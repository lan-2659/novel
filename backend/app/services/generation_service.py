import json
from typing import Any, Iterator

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..context_builder import tail_of
from ..llm.deepseek_client import LLMClient
from ..models.entities import Chapter, Project
from ..pipeline import prompts
from ..pipeline.stages import (
    STAGE_CHAPTER_PLAN,
    STAGE_COMPLETED,
    STAGE_OUTLINE,
    STAGE_SETTING,
    STAGE_WRITING,
    advance_stage,
)
from ..repositories.content_repo import ContentRepository
from ..repositories.project_repo import ProjectRepository


class GenerationService:
    def __init__(self, db: Session, llm: LLMClient) -> None:
        self.db = db
        self.llm = llm
        self.projects = ProjectRepository(db)
        self.content = ContentRepository(db)

    def _get_project(self, project_id: int) -> Project:
        project = self.projects.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        return project

    # ---- 故事设定 ----
    def generate_setting(self, project_id: int):
        project = self._get_project(project_id)
        system, user = prompts.build_setting_messages(project.premise)
        data = self.llm.generate_json(system, user)
        setting = self.content.save_setting(project_id, data)
        project.stage = advance_stage(project.stage, STAGE_SETTING)
        self.db.commit()
        return setting

    def save_setting(self, project_id: int, content: dict[str, Any]):
        project = self._get_project(project_id)
        setting = self.content.save_setting(project_id, content)
        project.stage = advance_stage(project.stage, STAGE_SETTING)
        self.db.commit()
        return setting

    # ---- 故事大纲 ----
    def generate_outline(self, project_id: int):
        project = self._get_project(project_id)
        setting = self.content.get_setting(project_id)
        if not setting:
            raise HTTPException(status_code=409, detail="请先生成故事设定")
        system, user = prompts.build_outline_messages(project.premise, setting.content)
        data = self.llm.generate_json(system, user)
        outline = self.content.save_outline(project_id, data)
        project.stage = advance_stage(project.stage, STAGE_OUTLINE)
        self.db.commit()
        return outline

    def save_outline(self, project_id: int, content: dict[str, Any]):
        project = self._get_project(project_id)
        outline = self.content.save_outline(project_id, content)
        project.stage = advance_stage(project.stage, STAGE_OUTLINE)
        self.db.commit()
        return outline

    # ---- 章节规划 ----
    def generate_chapter_plan(self, project_id: int):
        project = self._get_project(project_id)
        setting = self.content.get_setting(project_id)
        outline = self.content.get_outline(project_id)
        if not setting or not outline:
            raise HTTPException(status_code=409, detail="请先生成故事设定与大纲")
        system, user = prompts.build_chapter_plan_messages(
            project.premise, setting.content, outline.content
        )
        data = self.llm.generate_json(system, user)
        plan = self.content.save_plan(project_id, data)
        project.stage = advance_stage(project.stage, STAGE_CHAPTER_PLAN)
        self.db.commit()
        return plan

    def save_chapter_plan(self, project_id: int, content: dict[str, Any]):
        project = self._get_project(project_id)
        plan = self.content.save_plan(project_id, content)
        project.stage = advance_stage(project.stage, STAGE_CHAPTER_PLAN)
        self.db.commit()
        return plan

    # ---- 章节 ----
    def list_chapters(self, project_id: int) -> list[Chapter]:
        self._get_project(project_id)
        return self.content.list_chapters(project_id)

    def get_chapter(self, chapter_id: int) -> Chapter:
        chapter = self.content.get_chapter(chapter_id)
        if not chapter:
            raise HTTPException(status_code=404, detail="章节不存在")
        return chapter

    def update_chapter(
        self,
        chapter_id: int,
        title: str | None = None,
        content: str | None = None,
        status: str | None = None,
    ) -> Chapter:
        chapter = self.get_chapter(chapter_id)
        if status is not None and status not in ("draft", "confirmed"):
            raise HTTPException(status_code=400, detail="非法章节状态")
        chapter = self.content.update_chapter(
            chapter, title=title, content=content, status=status
        )
        if status == "confirmed":
            self._maybe_complete(chapter.project_id)
        return chapter

    def ensure_can_generate_chapter(self, project_id: int) -> None:
        project = self._get_project(project_id)
        if not self.content.get_setting(project_id):
            raise HTTPException(status_code=409, detail="请先生成故事设定")
        if not self.content.get_plan(project_id):
            raise HTTPException(status_code=409, detail="请先生成章节规划")
        if project.stage == STAGE_COMPLETED:
            raise HTTPException(status_code=409, detail="本书所有章节已完成")

    def stream_next_chapter(self, project_id: int) -> Iterator[dict[str, Any]]:
        project = self._get_project(project_id)
        plan = self.content.get_plan(project_id)
        setting = self.content.get_setting(project_id)
        chapters = self._plan_chapters(plan.content if plan else None)

        existing = self.content.list_chapters(project_id)
        next_number = (max(c.number for c in existing) if existing else 0) + 1
        title = self._chapter_title(chapters, next_number)

        chapter = self.content.create_chapter(
            project_id, next_number, title=title, status="generating"
        )
        yield from self._stream_chapter(project, chapter, chapters, setting.content)

    def stream_regenerate_chapter(self, chapter_id: int) -> Iterator[dict[str, Any]]:
        chapter = self.get_chapter(chapter_id)
        project = self._get_project(chapter.project_id)
        plan = self.content.get_plan(chapter.project_id)
        setting = self.content.get_setting(chapter.project_id)
        chapters = self._plan_chapters(plan.content if plan else None)

        chapter.status = "generating"
        self.db.commit()
        yield from self._stream_chapter(
            project, chapter, chapters, setting.content if setting else {}
        )

    def _stream_chapter(
        self,
        project: Project,
        chapter: Chapter,
        chapters: list[dict[str, Any]],
        setting: dict[str, Any],
    ) -> Iterator[dict[str, Any]]:
        prev_tail = self._previous_tail(project.id, chapter.number)
        system, user = prompts.build_chapter_messages(
            project.premise, setting, chapters, chapter.number, prev_tail
        )
        acc: list[str] = []
        try:
            for token in self.llm.stream_text(system, user):
                acc.append(token)
                yield {"type": "token", "content": token}
        except Exception as exc:
            self.content.update_chapter(chapter, status="failed", content="".join(acc))
            yield {"type": "error", "message": str(exc)}
            return

        content = "".join(acc)
        self.content.update_chapter(chapter, content=content, status="draft")
        project.stage = advance_stage(project.stage, STAGE_WRITING)
        self._maybe_complete(project.id)
        self.db.commit()
        yield {
            "type": "done",
            "chapter": {
                "id": chapter.id,
                "number": chapter.number,
                "title": chapter.title,
                "status": chapter.status,
            },
        }

    def _previous_tail(self, project_id: int, number: int) -> str:
        prev = next(
            (c for c in self.content.list_chapters(project_id) if c.number == number - 1),
            None,
        )
        return tail_of(prev.content, 800) if prev else ""

    @staticmethod
    def _plan_chapters(plan_content: dict[str, Any] | None) -> list[dict[str, Any]]:
        if isinstance(plan_content, dict):
            chapters = plan_content.get("chapters", [])
            if isinstance(chapters, list):
                return chapters
        return []

    @staticmethod
    def _chapter_title(chapters: list[dict[str, Any]], number: int) -> str:
        target = next(
            (c for c in chapters if int(c.get("number", 0)) == number), None
        )
        return target.get("title", "") if target else f"第{number}章"

    def _maybe_complete(self, project_id: int) -> None:
        project = self.projects.get(project_id)
        if not project:
            return
        plan = self.content.get_plan(project_id)
        plan_numbers = {
            int(c["number"])
            for c in self._plan_chapters(plan.content if plan else None)
            if isinstance(c, dict) and c.get("number") is not None
        }
        confirmed_numbers = {
            c.number for c in self.content.list_chapters(project_id)
            if c.status == "confirmed"
        }
        if plan_numbers and plan_numbers.issubset(confirmed_numbers):
            project.stage = STAGE_COMPLETED

    # ---- 导出 ----
    def export(self, project_id: int) -> str:
        project = self._get_project(project_id)
        setting = self.content.get_setting(project_id)
        outline = self.content.get_outline(project_id)
        plan = self.content.get_plan(project_id)
        chapters = self.content.list_chapters(project_id)

        lines = [f"# {project.title}", "", "## 创意", project.premise, ""]
        if setting:
            lines += ["## 故事设定", json.dumps(setting.content, ensure_ascii=False, indent=2), ""]
        if outline:
            lines += ["## 大纲", json.dumps(outline.content, ensure_ascii=False, indent=2), ""]
        if plan:
            lines += ["## 章节规划", json.dumps(plan.content, ensure_ascii=False, indent=2), ""]
        lines += ["## 正文", ""]
        for chapter in chapters:
            lines += [f"### 第{chapter.number}章 {chapter.title}", "", chapter.content, ""]
        return "\n".join(lines)
