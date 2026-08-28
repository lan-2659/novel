"""全书级内容生成：故事设定与全书大纲。

章节规划与章节正文生成已迁移到 VolumeService（按卷生成）。
全书大纲生成后会自动创建第一卷，保证写作流程不中断。
"""

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..llm.deepseek_client import LLMClient
from ..models.entities import Project
from ..pipeline import prompts
from ..pipeline.stages import STAGE_OUTLINE, STAGE_SETTING, advance_stage
from ..repositories.content_repo import ContentRepository
from ..repositories.project_repo import ProjectRepository
from ..repositories.volume_repo import VolumeRepository


class GenerationService:
    def __init__(self, db: Session, llm: LLMClient) -> None:
        self.db = db
        self.llm = llm
        self.projects = ProjectRepository(db)
        self.content = ContentRepository(db)
        self.volumes = VolumeRepository(db)

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

    # ---- 全书大纲 ----
    def generate_outline(self, project_id: int):
        project = self._get_project(project_id)
        setting = self.content.get_setting(project_id)
        if not setting:
            raise HTTPException(status_code=409, detail="请先生成故事设定")
        system, user = prompts.build_outline_messages(project.premise, setting.content)
        data = self.llm.generate_json(system, user)
        outline = self.content.save_outline(project_id, data)
        project.stage = advance_stage(project.stage, STAGE_OUTLINE)
        self._ensure_initial_volume(project)
        self.db.commit()
        return outline

    def save_outline(self, project_id: int, content: dict[str, Any]):
        project = self._get_project(project_id)
        outline = self.content.save_outline(project_id, content)
        project.stage = advance_stage(project.stage, STAGE_OUTLINE)
        self._ensure_initial_volume(project)
        self.db.commit()
        return outline

    def _ensure_initial_volume(self, project: Project) -> None:
        """全书大纲就绪后自动创建第一卷并设为当前卷。"""
        if self.volumes.list(project.id):
            return
        volume = self.volumes.create(project.id, 1)
        project.current_volume_id = volume.id

