import json
from typing import Iterator, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ..schemas.entities import ChapterOut, ChapterPage, ChapterUpdate
from ..services.volume_service import VolumeService
from .deps import get_volume_service

router = APIRouter()


def _sse(gen: Iterator[dict]) -> StreamingResponse:
    def event_stream():
        for event in gen:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/projects/{project_id}/chapters")
def generate_next_chapter(
    project_id: int,
    svc: VolumeService = Depends(get_volume_service),
):
    """兼容入口：在当前卷内生成下一章（新流程请用 /api/volumes/{id}/chapters）。"""
    volume = svc.current_volume(project_id)
    svc.ensure_can_generate_chapter(volume.id)
    return _sse(svc.stream_next_chapter(volume.id))


@router.get("/projects/{project_id}/chapters", response_model=ChapterPage)
def list_chapters(
    project_id: int,
    volume_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
    svc: VolumeService = Depends(get_volume_service),
):
    return svc.list_chapters(
        project_id=project_id, volume_id=volume_id, page=page, page_size=page_size
    )


@router.get("/chapters/{chapter_id}", response_model=ChapterOut)
def get_chapter(
    chapter_id: int,
    svc: VolumeService = Depends(get_volume_service),
):
    return svc.get_chapter(chapter_id)


@router.put("/chapters/{chapter_id}", response_model=ChapterOut)
def update_chapter(
    chapter_id: int,
    payload: ChapterUpdate,
    svc: VolumeService = Depends(get_volume_service),
):
    return svc.update_chapter(chapter_id, payload.title, payload.content, payload.status)


@router.post("/chapters/{chapter_id}/regenerate")
def regenerate_chapter(
    chapter_id: int,
    svc: VolumeService = Depends(get_volume_service),
):
    svc.get_chapter(chapter_id)  # 校验章节存在
    return _sse(svc.stream_regenerate_chapter(chapter_id))
