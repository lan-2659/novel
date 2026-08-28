from fastapi.testclient import TestClient

from .conftest import create_project, sse_events


def _setup_to_outline(client: TestClient, pid: int) -> int:
    """设定 + 全书大纲，返回自动创建的第一卷 id。"""
    assert client.post(f"/api/projects/{pid}/settings").status_code == 200
    assert client.post(f"/api/projects/{pid}/outline").status_code == 200
    detail = client.get(f"/api/projects/{pid}").json()
    assert len(detail["volumes"]) == 1
    assert detail["current_volume_id"] == detail["volumes"][0]["id"]
    return detail["volumes"][0]["id"]


def test_health(client: TestClient):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_and_list_project(client: TestClient):
    pid = create_project(client)
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    assert any(p["id"] == pid for p in resp.json())


def test_create_project_rejects_empty_premise(client: TestClient):
    resp = client.post("/api/projects", json={"premise": "  "})
    assert resp.status_code == 400


def test_generate_outline_requires_setting(client: TestClient):
    pid = create_project(client)
    resp = client.post(f"/api/projects/{pid}/outline")
    assert resp.status_code == 409


def test_generate_chapter_requires_plan(client: TestClient):
    pid = create_project(client)
    vol_id = _setup_to_outline(client, pid)
    resp = client.post(f"/api/volumes/{vol_id}/chapters")
    assert resp.status_code == 409


def test_full_flow_volume_based(client: TestClient):
    pid = create_project(client)

    # 设定
    resp = client.post(f"/api/projects/{pid}/settings")
    assert resp.status_code == 200
    assert resp.json()["content"]["worldview"] == "测试世界观"

    # 全书大纲 -> 自动创建第一卷
    vol_id = _setup_to_outline(client, pid)

    # 卷大纲
    resp = client.post(f"/api/volumes/{vol_id}/outline")
    assert resp.status_code == 200
    assert resp.json()["outline"]["summary"] == "第一卷测试大纲"

    # 卷章节规划
    resp = client.post(f"/api/volumes/{vol_id}/chapter-plan")
    assert resp.status_code == 200
    assert len(resp.json()["chapter_plan"]["chapters"]) == 2

    # 卷内生成第一章（SSE）
    resp = client.post(f"/api/volumes/{vol_id}/chapters")
    assert resp.status_code == 200
    events = sse_events(resp.text)
    tokens = "".join(e["content"] for e in events if e["type"] == "token")
    assert "测试正文" in tokens
    assert any(e["type"] == "done" for e in events)

    # 章节列表：volume_id 过滤 + 分页
    resp = client.get(
        f"/api/projects/{pid}/chapters?volume_id={vol_id}&page=1&page_size=10"
    )
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["volume_id"] == vol_id

    # 卷详情包含章节
    resp = client.get(f"/api/volumes/{vol_id}")
    assert resp.status_code == 200
    assert len(resp.json()["chapters"]) == 1

    # 确认章节 -> 触发追踪更新
    chapter_id = data["items"][0]["id"]
    resp = client.put(f"/api/chapters/{chapter_id}", json={"status": "confirmed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"

    detail = client.get(f"/api/projects/{pid}").json()
    assert "第1章后" in detail["character_state_summary"]
    assert "神秘符号再次出现" in detail["foreshadowing_items"]
    assert "本章张三发现了新的线索" in detail["global_summary"]
    vol = client.get(f"/api/volumes/{vol_id}").json()
    assert "本章张三发现了新的线索" in vol["summary"]

    # 卷导出 + 全书合并导出
    resp = client.get(f"/api/volumes/{vol_id}/export")
    assert resp.status_code == 200
    assert "测试正文" in resp.json()["markdown"]
    resp = client.get(f"/api/projects/{pid}/export")
    assert resp.status_code == 200
    assert "测试正文" in resp.json()["markdown"]


def test_continue_writing(client: TestClient):
    pid = create_project(client)
    vol_id = _setup_to_outline(client, pid)
    client.post(f"/api/volumes/{vol_id}/outline")
    client.post(f"/api/volumes/{vol_id}/chapter-plan")

    # 生成第一章并确认
    client.post(f"/api/volumes/{vol_id}/chapters")
    chapters = client.get(f"/api/volumes/{vol_id}/chapters").json()
    client.put(f"/api/chapters/{chapters[0]['id']}", json={"status": "confirmed"})

    # 继续写作 -> 生成第二章（卷内）
    resp = client.post(f"/api/volumes/{vol_id}/chapters")
    assert resp.status_code == 200
    chapters = client.get(f"/api/volumes/{vol_id}/chapters").json()
    assert len(chapters) == 2
    assert chapters[1]["number"] == 2


def test_volume_completion_advances_to_next(client: TestClient):
    pid = create_project(client)
    vol1 = _setup_to_outline(client, pid)

    # 创建第二卷（当前卷仍是 vol1）
    resp = client.post(f"/api/projects/{pid}/volumes", json={"title": "第二卷"})
    assert resp.status_code == 201
    vol2 = resp.json()["id"]
    detail = client.get(f"/api/projects/{pid}").json()
    assert detail["current_volume_id"] == vol1

    # 第一卷：1 章规划 -> 写 1 章 -> 确认 -> 卷完成 -> 当前卷推进到 vol2
    client.put(
        f"/api/volumes/{vol1}/chapter-plan",
        json={"content": {"chapters": [{"number": 1, "title": "终章", "summary": "结束"}]}},
    )
    client.post(f"/api/volumes/{vol1}/chapters")
    ch = client.get(f"/api/volumes/{vol1}/chapters").json()[0]
    client.put(f"/api/chapters/{ch['id']}", json={"status": "confirmed"})

    detail = client.get(f"/api/projects/{pid}").json()
    assert detail["volumes"][0]["status"] == "completed"
    assert detail["volumes"][0]["stage"] == "volume_completed"
    assert detail["current_volume_id"] == vol2
    assert detail["stage"] == "writing"


def test_project_completed_when_all_volumes_done(client: TestClient):
    pid = create_project(client)
    vol1 = _setup_to_outline(client, pid)

    client.put(
        f"/api/volumes/{vol1}/chapter-plan",
        json={"content": {"chapters": [{"number": 1, "title": "终章", "summary": "结束"}]}},
    )
    client.post(f"/api/volumes/{vol1}/chapters")
    ch = client.get(f"/api/volumes/{vol1}/chapters").json()[0]
    client.put(f"/api/chapters/{ch['id']}", json={"status": "confirmed"})

    detail = client.get(f"/api/projects/{pid}").json()
    assert detail["stage"] == "completed"


def test_edit_setting_is_used_in_detail(client: TestClient):
    pid = create_project(client)
    client.post(f"/api/projects/{pid}/settings")
    resp = client.put(
        f"/api/projects/{pid}/settings",
        json={"content": {"worldview": "手工修改的世界观"}},
    )
    assert resp.status_code == 200
    detail = client.get(f"/api/projects/{pid}").json()
    assert detail["setting"]["worldview"] == "手工修改的世界观"


def test_legacy_project_chapter_endpoint_delegates_to_current_volume(client: TestClient):
    pid = create_project(client)
    vol_id = _setup_to_outline(client, pid)
    client.post(f"/api/volumes/{vol_id}/outline")
    client.post(f"/api/volumes/{vol_id}/chapter-plan")
    resp = client.post(f"/api/projects/{pid}/chapters")
    assert resp.status_code == 200
    assert any(e["type"] == "done" for e in sse_events(resp.text))


def test_generate_ideas(client: TestClient):
    # 默认 / 指定 count：返回结构完整
    resp = client.post("/api/ideas/generate", json={"count": 5})
    assert resp.status_code == 200
    ideas = resp.json()["ideas"]
    assert len(ideas) == 3  # FakeLLM 固定返回 3 条
    for idea in ideas:
        assert "title" in idea and "idea" in idea and "genre" in idea and "hook" in idea

    # 题材 / 风格透传
    resp = client.post(
        "/api/ideas/generate",
        json={"count": 3, "genre": "悬疑", "style": "烧脑"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["ideas"]) == 3

    # count 越界返回 400
    assert client.post("/api/ideas/generate", json={"count": 0}).status_code == 400
    assert client.post("/api/ideas/generate", json={"count": 6}).status_code == 400

    # 默认 count 生效
    resp = client.post("/api/ideas/generate", json={})
    assert resp.status_code == 200
    assert resp.json()["ideas"]

