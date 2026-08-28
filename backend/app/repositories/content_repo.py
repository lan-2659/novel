from typing import Any

from sqlalchemy.orm import Session

from ..models.entities import Chapter, StoryOutline, StorySetting


class ContentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- 故事设定（全书级）----
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

    # ---- 故事大纲（全书级）----
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

    # ---- 章节 ----
    def list_chapters(
        self,
        project_id: int | None = None,
        volume_id: int | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[Chapter]:
        query = self.db.query(Chapter)
        if project_id is not None:
            query = query.filter_by(project_id=project_id)
        if volume_id is not None:
            query = query.filter_by(volume_id=volume_id)
        query = query.order_by(Chapter.number)
        if limit is not None:
            query = query.offset(offset).limit(limit)
        return query.all()

    def count_chapters(
        self,
        project_id: int | None = None,
        volume_id: int | None = None,
    ) -> int:
        query = self.db.query(Chapter)
        if project_id is not None:
            query = query.filter_by(project_id=project_id)
        if volume_id is not None:
            query = query.filter_by(volume_id=volume_id)
        return query.count()

    def count_confirmed_chapters(
        self,
        project_id: int | None = None,
        volume_id: int | None = None,
    ) -> int:
        query = self.db.query(Chapter).filter(Chapter.status == "confirmed")
        if project_id is not None:
            query = query.filter_by(project_id=project_id)
        if volume_id is not None:
            query = query.filter_by(volume_id=volume_id)
        return query.count()

    def max_chapter_number(self, project_id: int) -> int:
        row = (
            self.db.query(Chapter.number)
            .filter_by(project_id=project_id)
            .order_by(Chapter.number.desc())
            .first()
        )
        return row[0] if row else 0

    def volume_chapter_position(self, volume_id: int, chapter_number: int) -> int:
        """返回章节在卷内的 1-based 位置，用于匹配卷章节规划。"""
        return (
            self.db.query(Chapter)
            .filter(Chapter.volume_id == volume_id, Chapter.number <= chapter_number)
            .count()
        )

    def get_chapter(self, chapter_id: int) -> Chapter | None:
        return self.db.get(Chapter, chapter_id)

    def create_chapter(
        self,
        project_id: int,
        volume_id: int,
        number: int,
        title: str = "",
        content: str = "",
        status: str = "generating",
    ) -> Chapter:
        chapter = Chapter(
            project_id=project_id,
            volume_id=volume_id,
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
