from fastapi.testclient import TestClient

from .conftest import create_project, sse_events


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
    client.post(f"/api/projects/{pid}/settings")
    resp = client.post(f"/api/projects/{pid}/chapters")
    assert resp.status_code == 409


def test_full_flow(client: TestClient):
    pid = create_project(client)

    # 设定
    resp = client.post(f"/api/projects/{pid}/settings")
    assert resp.status_code == 200
    assert resp.json()["content"]["worldview"] == "测试世界观"

    # 大纲
    resp = client.post(f"/api/projects/{pid}/outline")
    assert resp.status_code == 200
    assert resp.json()["content"]["summary"] == "测试梗概"

    # 章节规划
    resp = client.post(f"/api/projects/{pid}/chapter-plan")
    assert resp.status_code == 200
    assert len(resp.json()["content"]["chapters"]) == 2

    # 生成第一章（SSE）
    resp = client.post(f"/api/projects/{pid}/chapters")
    assert resp.status_code == 200
    events = sse_events(resp.text)
    tokens = "".join(e["content"] for e in events if e["type"] == "token")
    assert "测试正文" in tokens
    assert any(e["type"] == "done" for e in events)

    # 章节列表
    resp = client.get(f"/api/projects/{pid}/chapters")
    chapters = resp.json()
    assert len(chapters) == 1
    assert chapters[0]["status"] == "draft"

    # 确认章节
    chapter_id = chapters[0]["id"]
    resp = client.put(f"/api/chapters/{chapter_id}", json={"status": "confirmed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"

    # 导出
    resp = client.get(f"/api/projects/{pid}/export")
    assert resp.status_code == 200
    assert "测试正文" in resp.json()["markdown"]


def test_continue_writing(client: TestClient):
    pid = create_project(client)
    client.post(f"/api/projects/{pid}/settings")
    client.post(f"/api/projects/{pid}/outline")
    client.post(f"/api/projects/{pid}/chapter-plan")

    # 生成第一章并确认
    client.post(f"/api/projects/{pid}/chapters")
    chapters = client.get(f"/api/projects/{pid}/chapters").json()
    client.put(f"/api/chapters/{chapters[0]['id']}", json={"status": "confirmed"})

    # 继续写作 -> 生成第二章
    resp = client.post(f"/api/projects/{pid}/chapters")
    assert resp.status_code == 200
    chapters = client.get(f"/api/projects/{pid}/chapters").json()
    assert len(chapters) == 2
    assert chapters[1]["number"] == 2


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
