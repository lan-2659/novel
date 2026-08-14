from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    premise: str
    title: Optional[str] = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    premise: str
    stage: str


class ContentIn(BaseModel):
    content: dict[str, Any]


class SettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: int
    content: dict[str, Any]
    version: int


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None


class ChapterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    number: int
    title: str
    content: str
    status: str


class ProjectDetail(BaseModel):
    id: int
    title: str
    premise: str
    stage: str
    setting: Optional[dict[str, Any]] = None
    outline: Optional[dict[str, Any]] = None
    chapter_plan: Optional[dict[str, Any]] = None
    chapters: list[ChapterOut] = []
