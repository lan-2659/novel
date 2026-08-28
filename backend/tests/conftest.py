import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_llm_client
from app.database import Base, get_db
from app.main import app


class FakeLLM:
    """假 LLM：返回确定性内容，避免测试依赖外部 API。按 system prompt 分支。"""

    def generate_json(self, system: str, user: str) -> dict:
        if "创意策划师" in system:  # 首页 AI 灵感创意
            return {
                "ideas": [
                    {
                        "title": "不存在的第13号病房",
                        "idea": "一名实习医生发现医院里有一间不存在于任何建筑记录中的病房，而所有进入过这里的病人都声称自己曾经见过未来。",
                        "genre": "悬疑",
                        "hook": "医院没有第13号病房，但每天凌晨13:13，电梯都会自动停在那里。",
                    },
                    {
                        "title": "倒数第二次人生",
                        "idea": "主角死后发现自己还能再活一次，但那是最后一次。",
                        "genre": "科幻",
                        "hook": "如果人生可以重来，但只有最后一次机会呢？",
                    },
                    {
                        "title": "雨巷裁缝铺",
                        "idea": "一间只在雨天营业的裁缝铺，能缝补被时间撕破的记忆。",
                        "genre": "都市",
                        "hook": "她的剪刀能剪开记忆，却缝不上自己的过去。",
                    },
                ]
            }
        if "编剧助理" in system:  # 追踪提取
            return {
                "character_changes": "主角张三状态稳定，与苏瑶关系进一步加深",
                "new_foreshadowing": ["神秘符号再次出现"],
                "resolved_foreshadowing": [],
                "chapter_summary": "本章张三发现了新的线索",
            }
        if "分卷规划师" in system:  # 卷章节规划
            return {
                "chapters": [
                    {"number": 1, "title": "第一章 开端", "summary": "故事开始"},
                    {"number": 2, "title": "第二章 发展", "summary": "情节推进"},
                ]
            }
        if "分卷策划师" in system:  # 卷大纲
            return {
                "summary": "第一卷测试大纲",
                "beats": [{"title": "开端", "summary": "故事开始"}],
            }
        if "策划师" in system:  # 全书大纲
            return {"summary": "测试梗概", "acts": [{"title": "第一幕", "summary": "开端"}]}
        return {  # 设定
            "worldview": "测试世界观",
            "characters": [{"name": "张三", "role": "主角", "description": "测试角色"}],
            "style": "第三人称",
        }

    def stream_text(self, system: str, user: str):
        yield "这是第一章的测试正文。"


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_llm_client] = lambda: FakeLLM()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def create_project(client: TestClient, premise: str = "一个失去记忆的侦探") -> int:
    resp = client.post("/api/projects", json={"premise": premise})
    assert resp.status_code == 201
    return resp.json()["id"]


def sse_events(text: str) -> list[dict]:
    events = []
    for chunk in text.split("\n\n"):
        chunk = chunk.strip()
        for line in chunk.split("\n"):
            if line.startswith("data: "):
                import json

                events.append(json.loads(line[6:]))
    return events

