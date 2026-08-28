"""卷（Volume）维度业务逻辑：卷 CRUD、卷大纲/规划生成、卷内章节生成、追踪触发、导出。"""

import json
from typing import Any, Iterator

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..context_builder import ContextBuilder, tail_of
from ..llm.deepseek_client import LLMClient
from ..models.entities import Chapter, Project, Volume
from ..pipeline import prompts
from ..pipeline.stages import (
    STAGE_COMPLETED,
    STAGE_WRITING,
    VOLUME_STAGE_COMPLETED,
    VOLUME_STAGE_PLAN,
    VOLUME_STAGE_WRITING,
    VOLUME_STATUS_COMPLETED,
    VOLUME_STATUS_WRITING,
    advance_stage,
    advance_volume_stage,
)
from ..repositories.content_repo import ContentRepository
from ..repositories.project_repo import ProjectRepository
from ..repositories.volume_repo import VolumeRepository
from .tracking_service import TrackingService


class VolumeService:
    def __init__(self, db: Session, llm: LLMClient) -> None:
        self.db = db
        self.llm = llm
        self.projects = ProjectRepository(db)
        self.volumes = VolumeRepository(db)
        self.content = ContentRepository(db)
        self.context = ContextBuilder(db)
        self.tracking = TrackingService(db, llm)

    # ---------- 基础 ----------
    def _get_project(self, project_id: int) -> Project:
        project = self.projects.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        return project

    def _get_volume(self, volume_id: int) -> Volume:
        volume = self.volumes.get(volume_id)
        if not volume:
            raise HTTPException(status_code=404, detail="卷不存在")
        return volume

    def _setting(self, project_id: int):
        return self.content.get_setting(project_id)

    def _is_completed(self, volume_id: int) -> bool:
        volume = self.volumes.get(volume_id)
        return volume is None or volume.status == VOLUME_STATUS_COMPLETED

    # ---------- 卷 CRUD ----------
    def create_volume(self, project_id: int, title: str | None = None) -> Volume:
        project = self._get_project(project_id)
        number = self.volumes.next_number(project_id)
        volume = self.volumes.create(project_id, number, (title or "").strip())
        # 当前卷为空或已完结时，把新建卷设为当前卷
        if project.current_volume_id is None or self._is_completed(project.current_volume_id):
            project.current_volume_id = volume.id
            self.db.commit()
        return volume

    def list_volumes(self, project_id: int) -> list[Volume]:
        self._get_project(project_id)
        return self.volumes.list(project_id)

    def get_volume(self, volume_id: int) -> Volume:
        return self._get_volume(volume_id)

    def volume_detail(self, volume_id: int) -> dict[str, Any]:
        volume = self._get_volume(volume_id)
        return {
            **self._volume_dict(volume),
            "chapters": self.content.list_chapters(volume_id=volume_id),
        }

    def current_volume(self, project_id: int) -> Volume:
        project = self._get_project(project_id)
        if project.current_volume_id:
            volume = self.volumes.get(project.current_volume_id)
            if volume:
                return volume
        volumes = self.volumes.list(project_id)
        if volumes:
            return volumes[0]
        # 无任何卷时自动创建第一卷
        volume = self.volumes.create(project_id, 1)
        project.current_volume_id = volume.id
        self.db.commit()
        return volume

    def _volume_dict(self, volume: Volume) -> dict[str, Any]:
        return {
            "id": volume.id,
            "project_id": volume.project_id,
            "number": volume.number,
            "title": volume.title,
            "outline": volume.outline or None,
            "chapter_plan": volume.chapter_plan or None,
            "summary": volume.summary or "",
            "status": volume.status,
            "stage": volume.stage,
        }

    # ---------- 卷大纲 ----------
    def generate_volume_outline(self, volume_id: int) -> Volume:
        volume = self._get_volume(volume_id)
        project = self._get_project(volume.project_id)
        setting = self._setting(volume.project_id)
        if not setting:
            raise HTTPException(status_code=409, detail="请先生成故事设定")
        ctx = self.context.build_volume_outline_context(project, volume, setting)
        system, user = prompts.build_volume_outline_messages(
            ctx["premise"],
            ctx["setting"],
            ctx["global_outline_summary"],
            ctx["volume_number"],
            ctx["previous_volumes"],
        )
        data = self.llm.generate_json(system, user)
        self.volumes.save(volume, outline=data)
        volume.stage = advance_volume_stage(volume.stage, "volume_outline")
        self.db.commit()
        return volume

    def save_volume_outline(self, volume_id: int, content: dict[str, Any]) -> Volume:
        volume = self._get_volume(volume_id)
        self.volumes.save(volume, outline=content)
        volume.stage = advance_volume_stage(volume.stage, "volume_outline")
        self.db.commit()
        return volume

    # ---------- 卷章节规划 ----------
    def generate_volume_plan(self, volume_id: int) -> Volume:
        volume = self._get_volume(volume_id)
        project = self._get_project(volume.project_id)
        setting = self._setting(volume.project_id)
        if not setting:
            raise HTTPException(status_code=409, detail="请先生成故事设定")
        if not volume.outline:
            raise HTTPException(status_code=409, detail="请先生成卷大纲")
        ctx = self.context.build_volume_plan_context(project, volume, setting)
        system, user = prompts.build_volume_plan_messages(
            ctx["premise"],
            ctx["setting"],
            ctx["global_outline_summary"],
            ctx["volume_outline"],
            ctx["volume_number"],
            ctx["previous_volumes"],
            ctx["character_state_summary"],
            ctx["foreshadowing_items"],
            ctx["global_summary"],
        )
        data = self.llm.generate_json(system, user)
        self.volumes.save(volume, chapter_plan=data)
        volume.stage = advance_volume_stage(volume.stage, VOLUME_STAGE_PLAN)
        volume.status = VOLUME_STATUS_WRITING
        self.db.commit()
        return volume

    def save_volume_plan(self, volume_id: int, content: dict[str, Any]) -> Volume:
        volume = self._get_volume(volume_id)
        self.volumes.save(volume, chapter_plan=content)
        volume.stage = advance_volume_stage(volume.stage, VOLUME_STAGE_PLAN)
        volume.status = VOLUME_STATUS_WRITING
        self.db.commit()
        return volume

    # ---------- 章节 ----------
    def ensure_can_generate_chapter(self, volume_id: int) -> None:
        volume = self._get_volume(volume_id)
        project = self._get_project(volume.project_id)
        if project.stage == STAGE_COMPLETED:
            raise HTTPException(status_code=409, detail="本书所有卷已完成")
        if volume.status == VOLUME_STATUS_COMPLETED:
            raise HTTPException(status_code=409, detail="本卷已完成")
        if not volume.chapter_plan:
            raise HTTPException(status_code=409, detail="请先生成章节规划")

    def stream_next_chapter(self, volume_id: int) -> Iterator[dict[str, Any]]:
        volume = self._get_volume(volume_id)
        project = self._get_project(volume.project_id)
        setting = self._setting(volume.project_id)
        chapters = self._plan_chapters(volume.chapter_plan)

        local_number = self.content.count_chapters(volume_id=volume_id) + 1
        global_number = self.content.max_chapter_number(project.id) + 1
        title = self._chapter_title(chapters, local_number) or f"第{global_number}章"

        chapter = self.content.create_chapter(
            project.id, volume_id, global_number, title=title, status="generating"
        )
        yield from self._stream_chapter(
            project, volume, chapter, chapters, local_number, setting
        )

    def stream_regenerate_chapter(self, chapter_id: int) -> Iterator[dict[str, Any]]:
        chapter = self.get_chapter(chapter_id)
        volume = self._get_volume(chapter.volume_id) if chapter.volume_id else None
        if not volume:
            raise HTTPException(status_code=409, detail="章节未归属卷，无法重新生成")
        project = self._get_project(chapter.project_id)
        setting = self._setting(chapter.project_id)
        chapters = self._plan_chapters(volume.chapter_plan)
        local_number = self.content.volume_chapter_position(volume.id, chapter.number)

        chapter.status = "generating"
        self.db.commit()
        yield from self._stream_chapter(
            project, volume, chapter, chapters, local_number, setting
        )

    def _stream_chapter(
        self,
        project: Project,
        volume: Volume,
        chapter: Chapter,
        chapters: list[dict[str, Any]],
        local_number: int,
        setting: Any,
    ) -> Iterator[dict[str, Any]]:
        prev_tail = self._previous_tail(project.id, chapter.number)
        ctx = self.context.build_chapter_context(
            project, volume, setting, chapters, local_number, prev_tail
        )
        system, user = prompts.build_chapter_messages(ctx)
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
        volume.stage = advance_volume_stage(volume.stage, VOLUME_STAGE_WRITING)
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
            (
                c
                for c in self.content.list_chapters(project_id=project_id)
                if c.number == number - 1
            ),
            None,
        )
        return tail_of(prev.content, 800) if prev else ""

    def list_chapters(
        self,
        project_id: int | None = None,
        volume_id: int | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        page = max(1, page)
        page_size = min(max(1, page_size), 200)
        total = self.content.count_chapters(project_id=project_id, volume_id=volume_id)
        items = self.content.list_chapters(
            project_id=project_id,
            volume_id=volume_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def list_volume_chapters(self, volume_id: int) -> list[Chapter]:
        self._get_volume(volume_id)
        return self.content.list_chapters(volume_id=volume_id)

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
            # P1：确认后自动更新长期追踪信息（尽力而为）
            self.tracking.update_after_chapter_confirmed(chapter)
            self._maybe_complete_volume(chapter.volume_id)
        return chapter

    def _maybe_complete_volume(self, volume_id: int | None) -> None:
        if not volume_id:
            return
        volume = self.volumes.get(volume_id)
        if not volume:
            return
        plan = self._plan_chapters(volume.chapter_plan)
        if not plan:
            return
        confirmed = self.content.count_confirmed_chapters(volume_id=volume_id)
        if confirmed < len(plan):
            return
        volume.stage = advance_volume_stage(volume.stage, VOLUME_STAGE_COMPLETED)
        volume.status = VOLUME_STATUS_COMPLETED
        self.db.commit()
        self._advance_after_volume_completed(volume)

    def _advance_after_volume_completed(self, volume: Volume) -> None:
        project = self._get_project(volume.project_id)
        next_volume = self.volumes.get_by_number(project.id, volume.number + 1)
        if next_volume:
            project.current_volume_id = next_volume.id
        else:
            volumes = self.volumes.list(project.id)
            if volumes and all(v.status == VOLUME_STATUS_COMPLETED for v in volumes):
                project.stage = STAGE_COMPLETED
        self.db.commit()

    # ---------- 导出 ----------
    def export_volume(self, volume_id: int) -> str:
        volume = self._get_volume(volume_id)
        project = self._get_project(volume.project_id)
        chapters = self.content.list_chapters(volume_id=volume_id)

        lines = [f"# {project.title} · {volume.title}", ""]
        if volume.outline:
            lines += [
                "## 本卷大纲",
                json.dumps(volume.outline, ensure_ascii=False, indent=2),
                "",
            ]
        if volume.chapter_plan:
            lines += [
                "## 本卷章节规划",
                json.dumps(volume.chapter_plan, ensure_ascii=False, indent=2),
                "",
            ]
        lines += ["## 正文", ""]
        for chapter in chapters:
            lines += [
                f"### 第{chapter.number}章 {chapter.title}",
                "",
                chapter.content,
                "",
            ]
        return "\n".join(lines)

    def export_project(self, project_id: int) -> str:
        """合并导出全部卷（卷数多时可改为异步生成文件，MVP 同步返回）。"""
        project = self._get_project(project_id)
        setting = self.content.get_setting(project_id)
        outline = self.content.get_outline(project_id)

        lines = [f"# {project.title}", "", "## 创意", project.premise, ""]
        if setting:
            lines += [
                "## 故事设定",
                json.dumps(setting.content, ensure_ascii=False, indent=2),
                "",
            ]
        if outline:
            lines += [
                "## 全书大纲",
                json.dumps(outline.content, ensure_ascii=False, indent=2),
                "",
            ]
        for volume in self.volumes.list(project_id):
            lines += [f"## {volume.title}", ""]
            if volume.outline:
                lines += [
                    "### 本卷大纲",
                    json.dumps(volume.outline, ensure_ascii=False, indent=2),
                    "",
                ]
            for chapter in self.content.list_chapters(volume_id=volume.id):
                lines += [
                    f"#### 第{chapter.number}章 {chapter.title}",
                    "",
                    chapter.content,
                    "",
                ]
        return "\n".join(lines)

    # ---------- 工具 ----------
    @staticmethod
    def _plan_chapters(plan_content: Any) -> list[dict[str, Any]]:
        if isinstance(plan_content, dict):
            chapters = plan_content.get("chapters", [])
            if isinstance(chapters, list):
                return chapters
        return []

    @staticmethod
    def _chapter_title(chapters: list[dict[str, Any]], local_number: int) -> str:
        target = next(
            (c for c in chapters if int(c.get("number", 0)) == local_number),
            None,
        )
        return target.get("title", "") if target else ""
