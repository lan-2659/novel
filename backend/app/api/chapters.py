import json
from typing import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ..schemas.entities import ChapterOut, ChapterUpdate
from ..services.generation_service import GenerationService
from .deps import get_generation_service

router = APIRouter()


def _sse(gen: Iterator[dict]) -> StreamingResponse:
    def event_stream():
        for event in gen:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/projects/{project_id}/chapters")
def generate_next_chapter(
    project_id: int,
    svc: GenerationService = Depends(get_generation_service),
):
    svc.ensure_can_generate_chapter(project_id)
    return _sse(svc.stream_next_chapter(project_id))


@router.get("/projects/{project_id}/chapters", response_model=list[ChapterOut])
def list_chapters(
    project_id: int,
    svc: GenerationService = Depends(get_generation_service),
):
    return svc.list_chapters(project_id)


@router.get("/chapters/{chapter_id}", response_model=ChapterOut)
def get_chapter(
    chapter_id: int,
    svc: GenerationService = Depends(get_generation_service),
):
    return svc.get_chapter(chapter_id)


@router.put("/chapters/{chapter_id}", response_model=ChapterOut)
def update_chapter(
    chapter_id: int,
    payload: ChapterUpdate,
    svc: GenerationService = Depends(get_generation_service),
):
    return svc.update_chapter(chapter_id, payload.title, payload.content, payload.status)


@router.post("/chapters/{chapter_id}/regenerate")
def regenerate_chapter(
    chapter_id: int,
    svc: GenerationService = Depends(get_generation_service),
):
    svc.get_chapter(chapter_id)  # 校验章节存在
    return _sse(svc.stream_regenerate_chapter(chapter_id))


@router.get("/projects/{project_id}/export")
def export_project(
    project_id: int,
    svc: GenerationService = Depends(get_generation_service),
):
    return {"markdown": svc.export(project_id)}
