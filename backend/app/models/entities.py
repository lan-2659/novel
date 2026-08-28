from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from ..database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    premise = Column(Text, nullable=False)
    # 全书阶段：idea -> setting -> outline -> writing -> completed
    stage = Column(String(32), nullable=False, default="idea")
    # 当前卷（双层状态机，见 pipeline/stages.py）
    current_volume_id = Column(Integer, ForeignKey("volumes.id"), nullable=True)
    # 跨卷长期追踪（P1）：章节确认后由 TrackingService 自动更新
    character_state_summary = Column(Text, nullable=False, default="")
    foreshadowing_items = Column(JSON, nullable=False, default=list)
    global_summary = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    setting = relationship(
        "StorySetting", back_populates="project", uselist=False,
        cascade="all, delete-orphan",
    )
    outline = relationship(
        "StoryOutline", back_populates="project", uselist=False,
        cascade="all, delete-orphan",
    )
    volumes = relationship(
        "Volume",
        back_populates="project",
        foreign_keys="Volume.project_id",
        cascade="all, delete-orphan",
        order_by="Volume.number",
    )
    chapters = relationship(
        "Chapter", back_populates="project", cascade="all, delete-orphan",
    )
    current_volume = relationship(
        "Volume",
        foreign_keys="Project.current_volume_id",
        uselist=False,
        post_update=True,
    )


class StorySetting(Base):
    __tablename__ = "story_settings"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, unique=True)
    content = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project = relationship("Project", back_populates="setting")


class StoryOutline(Base):
    """全书级大纲（story_outlines），分卷大纲见 Volume.outline。"""

    __tablename__ = "story_outlines"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, unique=True)
    content = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project = relationship("Project", back_populates="outline")


class Volume(Base):
    """卷：长篇中的一级结构单元，每卷拥有独立大纲、章节规划与滚动摘要。"""

    __tablename__ = "volumes"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    number = Column(Integer, nullable=False, default=1)
    title = Column(String(200), nullable=False, default="")
    # 卷大纲 / 卷章节规划（JSON 文本存储，SQLite 中为 TEXT）
    outline = Column(JSON, nullable=False, default=dict)
    chapter_plan = Column(JSON, nullable=False, default=dict)
    # 本卷完成后的滚动剧情摘要，用于后续卷/章的上下文
    summary = Column(Text, nullable=False, default="")
    # 卷生命周期：draft -> writing -> completed
    status = Column(String(32), nullable=False, default="draft")
    # 卷内阶段：volume_outline -> volume_plan -> writing -> volume_completed
    stage = Column(String(32), nullable=False, default="volume_outline")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project = relationship(
        "Project", back_populates="volumes", foreign_keys=[project_id]
    )
    chapters = relationship("Chapter", back_populates="volume", cascade="all, delete-orphan")


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (
        # P3：长篇小说高频按 project/volume/number 过滤
        Index("ix_chapters_project_volume_number", "project_id", "volume_id", "number"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    volume_id = Column(Integer, ForeignKey("volumes.id"), nullable=True, index=True)
    number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False, default="")
    content = Column(Text, nullable=False, default="")
    status = Column(String(32), nullable=False, default="draft")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project = relationship("Project", back_populates="chapters")
    volume = relationship("Volume", back_populates="chapters")
