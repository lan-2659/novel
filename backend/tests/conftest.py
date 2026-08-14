import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_llm_client
from app.database import Base, get_db
from app.main import app


class FakeLLM:
    """假 LLM：返回确定性内容，避免测试依赖外部 API。"""

    def generate_json(self, system: str, user: str) -> dict:
        if "写作计划" in user:
            return {
                "chapters": [
                    {"number": 1, "title": "第一章 开端", "summary": "故事开始"},
                    {"number": 2, "title": "第二章 发展", "summary": "情节推进"},
                ]
            }
        if "大纲" in user:
            return {"summary": "测试梗概", "acts": [{"title": "第一幕", "summary": "开端"}]}
        return {
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
