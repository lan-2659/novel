from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from ..database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    premise = Column(Text, nullable=False)
    stage = Column(String(32), nullable=False, default="idea")
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
    plan = relationship(
        "ChapterPlan", back_populates="project", uselist=False,
        cascade="all, delete-orphan",
    )
    chapters = relationship(
        "Chapter", back_populates="project", cascade="all, delete-orphan",
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
    __tablename__ = "story_outlines"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, unique=True)
    content = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project = relationship("Project", back_populates="outline")


class ChapterPlan(Base):
    __tablename__ = "chapter_plans"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, unique=True)
    content = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project = relationship("Project", back_populates="plan")


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False, default="")
    content = Column(Text, nullable=False, default="")
    status = Column(String(32), nullable=False, default="draft")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project = relationship("Project", back_populates="chapters")
