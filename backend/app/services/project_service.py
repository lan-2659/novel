from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models.entities import Project
from ..repositories.content_repo import ContentRepository
from ..repositories.project_repo import ProjectRepository


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.projects = ProjectRepository(db)
        self.content = ContentRepository(db)

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
        plan = self.content.get_plan(project_id)
        chapters = self.content.list_chapters(project_id)
        return {
            "id": project.id,
            "title": project.title,
            "premise": project.premise,
            "stage": project.stage,
            "setting": setting.content if setting else None,
            "outline": outline.content if outline else None,
            "chapter_plan": plan.content if plan else None,
            "chapters": chapters,
        }
