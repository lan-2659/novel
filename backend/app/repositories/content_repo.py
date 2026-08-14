from typing import Any

from sqlalchemy.orm import Session

from ..models.entities import Chapter, ChapterPlan, StoryOutline, StorySetting


class ContentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- 故事设定 ----
    def get_setting(self, project_id: int) -> StorySetting | None:
        return self.db.query(StorySetting).filter_by(project_id=project_id).first()

    def save_setting(self, project_id: int, content: dict[str, Any]) -> StorySetting:
        row = self.get_setting(project_id)
        if row:
            row.content = content
            row.version += 1
        else:
            row = StorySetting(project_id=project_id, content=content, version=1)
            self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    # ---- 故事大纲 ----
    def get_outline(self, project_id: int) -> StoryOutline | None:
        return self.db.query(StoryOutline).filter_by(project_id=project_id).first()

    def save_outline(self, project_id: int, content: dict[str, Any]) -> StoryOutline:
        row = self.get_outline(project_id)
        if row:
            row.content = content
            row.version += 1
        else:
            row = StoryOutline(project_id=project_id, content=content, version=1)
            self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    # ---- 章节规划 ----
    def get_plan(self, project_id: int) -> ChapterPlan | None:
        return self.db.query(ChapterPlan).filter_by(project_id=project_id).first()

    def save_plan(self, project_id: int, content: dict[str, Any]) -> ChapterPlan:
        row = self.get_plan(project_id)
        if row:
            row.content = content
            row.version += 1
        else:
            row = ChapterPlan(project_id=project_id, content=content, version=1)
            self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    # ---- 章节 ----
    def list_chapters(self, project_id: int) -> list[Chapter]:
        return (
            self.db.query(Chapter)
            .filter_by(project_id=project_id)
            .order_by(Chapter.number)
            .all()
        )

    def get_chapter(self, chapter_id: int) -> Chapter | None:
        return self.db.get(Chapter, chapter_id)

    def create_chapter(
        self,
        project_id: int,
        number: int,
        title: str = "",
        content: str = "",
        status: str = "generating",
    ) -> Chapter:
        chapter = Chapter(
            project_id=project_id,
            number=number,
            title=title,
            content=content,
            status=status,
        )
        self.db.add(chapter)
        self.db.commit()
        self.db.refresh(chapter)
        return chapter

    def update_chapter(self, chapter: Chapter, **fields: Any) -> Chapter:
        for key, value in fields.items():
            if value is not None:
                setattr(chapter, key, value)
        self.db.commit()
        self.db.refresh(chapter)
        return chapter
