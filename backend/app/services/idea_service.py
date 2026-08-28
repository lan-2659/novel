"""首页 AI 灵感创意服务：调用 LLM 随机生成多个小说创意。

创意为一次性生成、随请求返回，不持久化到数据库。
"""

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..llm.deepseek_client import LLMClient
from ..pipeline import prompts

MIN_IDEAS = 1
MAX_IDEAS = 5


class IdeaService:
    def __init__(self, db: Session, llm: LLMClient) -> None:
        self.db = db
        self.llm = llm

    def generate_ideas(
        self,
        count: int = 5,
        genre: str | None = None,
        style: str | None = None,
    ) -> list[dict[str, str]]:
        if not MIN_IDEAS <= count <= MAX_IDEAS:
            raise HTTPException(
                status_code=400,
                detail=f"count 必须在 {MIN_IDEAS}~{MAX_IDEAS} 之间",
            )
        system, user = prompts.build_idea_messages(
            count, genre or None, style or None
        )
        data = self.llm.generate_json(system, user)
        raw = data.get("ideas", []) if isinstance(data, dict) else []
        ideas = [self._normalize(item) for item in raw if isinstance(item, dict)]
        return ideas[:count]

    @staticmethod
    def _normalize(item: dict[str, Any]) -> dict[str, str]:
        """字段归一化，保证前端拿到稳定的 title/idea/genre/hook 结构。"""
        return {
            "title": str(item.get("title") or "未命名创意"),
            "idea": str(item.get("idea") or item.get("summary") or ""),
            "genre": str(item.get("genre") or "未知"),
            "hook": str(item.get("hook") or ""),
        }
