from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models.entities import Project
from ..repositories.content_repo import ContentRepository
from ..repositories.project_repo import ProjectRepository
from ..repositories.volume_repo import VolumeRepository


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.projects = ProjectRepository(db)
        self.content = ContentRepository(db)
        self.volumes = VolumeRepository(db)

    def create(self, premise: str, title: str | None = None) -> Project:
        if not premise or not premise.strip():
            raise HTTPException(status_code=400, detail="创意不能为空")
        return self.projects.create(premise.strip(), title.strip() if title else None)

    def list(self) -> list[Project]:
        return self.projects.list()

    def get(self, project_id: int) -> Project:
        project = self.projects.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        return project

    def detail(self, project_id: int) -> dict:
        project = self.get(project_id)
        setting = self.content.get_setting(project_id)
        outline = self.content.get_outline(project_id)
        volumes = self.volumes.list(project_id)
        return {
            "id": project.id,
            "title": project.title,
            "premise": project.premise,
            "stage": project.stage,
            "current_volume_id": project.current_volume_id,
            "character_state_summary": project.character_state_summary or "",
            "foreshadowing_items": list(project.foreshadowing_items or []),
            "global_summary": project.global_summary or "",
            "setting": setting.content if setting else None,
            "outline": outline.content if outline else None,
            "volumes": volumes,
        }

