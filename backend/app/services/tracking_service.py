"""章节确认后的自动追踪更新（P1）。

流程：章节被确认 -> 调用 LLM 提取本章关键信息
（人物状态变化 / 新埋伏笔 / 已回收伏笔 / 剧情摘要）
-> 合并更新 Project 表的 character_state_summary / foreshadowing_items / global_summary
-> 更新 Volume 表的 summary。

尽力而为：LLM 提取失败不阻断章节确认，仅回滚本次追踪写入。
"""

from sqlalchemy.orm import Session

from ..llm.deepseek_client import LLMClient
from ..models.entities import Chapter, Project, Volume
from ..pipeline import prompts
from ..repositories.content_repo import ContentRepository
from ..repositories.project_repo import ProjectRepository
from ..repositories.volume_repo import VolumeRepository

CHARACTER_CAP = 6000
GLOBAL_SUMMARY_CAP = 6000
VOLUME_SUMMARY_CAP = 3000


class TrackingService:
    def __init__(self, db: Session, llm: LLMClient) -> None:
        self.db = db
        self.llm = llm
        self.projects = ProjectRepository(db)
        self.volumes = VolumeRepository(db)
        self.content = ContentRepository(db)

    def update_after_chapter_confirmed(self, chapter: Chapter) -> None:
        """尽力而为地更新追踪信息；失败仅回滚本次写入，不影响章节确认。"""
        project = self.projects.get(chapter.project_id)
        volume = self.volumes.get(chapter.volume_id) if chapter.volume_id else None
        if not project or not volume:
            return
        try:
            foreshadowing = list(project.foreshadowing_items or [])
            system, user = prompts.build_tracking_messages(
                chapter.title,
                chapter.content,
                project.character_state_summary or "",
                foreshadowing,
            )
            data = self.llm.generate_json(system, user)
            self._merge(project, volume, chapter, data)
        except Exception:
            self.db.rollback()

    def _merge(
        self,
        project: Project,
        volume: Volume,
        chapter: Chapter,
        data: dict,
    ) -> None:
        changes = str(data.get("character_changes") or "").strip()
        if changes:
            addition = f"### 第{chapter.number}章后\n{changes}\n"
            project.character_state_summary = _append_capped(
                project.character_state_summary, addition, CHARACTER_CAP
            )

        items = list(project.foreshadowing_items or [])
        for f in data.get("new_foreshadowing") or []:
            if f and f not in items:
                items.append(f)
        resolved = data.get("resolved_foreshadowing") or []
        if resolved:
            items = [i for i in items if i not in resolved]
        project.foreshadowing_items = items

        summary = str(data.get("chapter_summary") or "").strip()
        if summary:
            entry = f"第{chapter.number}章：{summary}\n"
            project.global_summary = _append_capped(project.global_summary, entry, GLOBAL_SUMMARY_CAP)
            volume.summary = _append_capped(volume.summary, entry, VOLUME_SUMMARY_CAP)

        self.db.commit()


def _append_capped(current: str, addition: str, cap: int) -> str:
    text = (current or "") + addition
    if len(text) > cap:
        text = text[-cap:]
    return text
