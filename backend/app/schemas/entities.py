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


class VolumeCreate(BaseModel):
    title: Optional[str] = None


class VolumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    number: int
    title: str
    outline: Optional[dict[str, Any]] = None
    chapter_plan: Optional[dict[str, Any]] = None
    summary: str = ""
    status: str = "draft"
    stage: str = "volume_outline"


class VolumeDetail(VolumeOut):
    chapters: list["ChapterOut"] = []


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None


class ChapterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    volume_id: Optional[int] = None
    number: int
    title: str
    content: str
    status: str


class ChapterPage(BaseModel):
    items: list[ChapterOut]
    total: int
    page: int
    page_size: int


class ProjectDetail(BaseModel):
    id: int
    title: str
    premise: str
    stage: str
    current_volume_id: Optional[int] = None
    character_state_summary: str = ""
    foreshadowing_items: list[str] = []
    global_summary: str = ""
    setting: Optional[dict[str, Any]] = None
    outline: Optional[dict[str, Any]] = None
    volumes: list[VolumeOut] = []


class IdeaRequest(BaseModel):
    count: int = 5
    genre: Optional[str] = None
    style: Optional[str] = None


class IdeaOut(BaseModel):
    title: str
    idea: str
    genre: str
    hook: str


class IdeaListOut(BaseModel):
    ideas: list[IdeaOut]
