"""分层上下文构建：为每一章/每一卷的生成组装足够且不过载的上下文。

策略（长篇小说系统核心）：
- 第一层 全书级固定信息：创意、世界观/人物设定、全书大纲摘要。
- 第二层 分卷级信息：本卷大纲、本卷章节规划中本章要点、本卷滚动摘要。
- 第三层 跨卷长期追踪：人物状态追踪、未解伏笔、全局滚动摘要。
- 第四层 近期上下文：上一章结尾（衔接文风与剧情）。
"""

from typing import Any

from sqlalchemy.orm import Session

from .models.entities import Project, Volume
from .repositories.content_repo import ContentRepository
from .repositories.volume_repo import VolumeRepository


def tail_of(text: str, n: int = 800) -> str:
    """截取文本末尾 n 个字符，用于章节衔接上下文。"""
    text = (text or "").strip()
    if len(text) <= n:
        return text
    return text[-n:]


class ContextBuilder:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.content = ContentRepository(db)
        self.volumes = VolumeRepository(db)

    # ---- 第一层：全书级固定信息 ----
    def _global_layer(self, project: Project, setting: Any) -> dict[str, Any]:
        outline = self.content.get_outline(project.id)
        outline_content = outline.content if outline else {}
        outline_summary = ""
        if isinstance(outline_content, dict):
            outline_summary = outline_content.get("summary", "") or ""
        return {
            "premise": project.premise,
            "setting": setting.content if setting else {},
            "outline_summary": outline_summary,
        }

    # ---- 第三层：跨卷长期追踪 ----
    def _tracking_layer(self, project: Project) -> dict[str, Any]:
        return {
            "character_state_summary": project.character_state_summary or "",
            "foreshadowing_items": project.foreshadowing_items or [],
            "global_summary": project.global_summary or "",
        }

    # ---- 卷大纲生成上下文 ----
    def build_volume_outline_context(
        self, project: Project, volume: Volume, setting: Any
    ) -> dict[str, Any]:
        global_ = self._global_layer(project, setting)
        return {
            "premise": global_["premise"],
            "setting": global_["setting"],
            "global_outline_summary": global_["outline_summary"],
            "volume_number": volume.number,
            "previous_volumes": self._previous_volumes_summary(project.id, volume.number),
        }

    # ---- 卷章节规划生成上下文（含前置卷摘要 + 跨卷追踪，实现后卷呼应前卷）----
    def build_volume_plan_context(
        self, project: Project, volume: Volume, setting: Any
    ) -> dict[str, Any]:
        global_ = self._global_layer(project, setting)
        tracking = self._tracking_layer(project)
        return {
            "premise": global_["premise"],
            "setting": global_["setting"],
            "global_outline_summary": global_["outline_summary"],
            "volume_number": volume.number,
            "volume_outline": volume.outline if isinstance(volume.outline, dict) else {},
            "previous_volumes": self._previous_volumes_summary(project.id, volume.number),
            "character_state_summary": tracking["character_state_summary"],
            "foreshadowing_items": tracking["foreshadowing_items"],
            "global_summary": tracking["global_summary"],
        }

    # ---- 章节生成四层上下文 ----
    def build_chapter_context(
        self,
        project: Project,
        volume: Volume,
        setting: Any,
        chapters: list[dict[str, Any]],
        local_number: int,
        prev_tail: str,
    ) -> dict[str, Any]:
        global_ = self._global_layer(project, setting)
        tracking = self._tracking_layer(project)

        current_summary = ""
        current_title = ""
        for c in chapters:
            if int(c.get("number", 0)) == local_number:
                current_summary = c.get("summary", "") or ""
                current_title = c.get("title", "") or ""
                break

        return {
            # 第一层：全书级
            "premise": global_["premise"],
            "setting": global_["setting"],
            "outline_summary": global_["outline_summary"],
            # 第二层：分卷级
            "volume_title": volume.title,
            "volume_outline": volume.outline if isinstance(volume.outline, dict) else {},
            "volume_summary": volume.summary or "",
            "current_chapter_title": current_title,
            "current_chapter_summary": current_summary,
            # 第三层：跨卷追踪
            "character_state_summary": tracking["character_state_summary"],
            "foreshadowing_items": tracking["foreshadowing_items"],
            "global_summary": tracking["global_summary"],
            # 第四层：近期上下文
            "prev_tail": prev_tail,
        }

    def _previous_volumes_summary(self, project_id: int, volume_number: int) -> list[dict[str, str]]:
        vols = self.volumes.list(project_id)
        return [
            {"number": v.number, "title": v.title, "summary": v.summary or ""}
            for v in vols
            if v.number < volume_number
        ]

