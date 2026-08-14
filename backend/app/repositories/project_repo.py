from sqlalchemy.orm import Session

from ..models.entities import Project


class ProjectRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, premise: str, title: str | None = None) -> Project:
        project = Project(
            title=(title or premise[:30]),
            premise=premise,
            stage="idea",
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def list(self) -> list[Project]:
        return self.db.query(Project).order_by(Project.updated_at.desc()).all()

    def get(self, project_id: int) -> Project | None:
        return self.db.get(Project, project_id)
