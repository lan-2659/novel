import json
from typing import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ..schemas.entities import ChapterOut, ContentIn, VolumeDetail, VolumeOut
from ..services.volume_service import VolumeService
from .deps import get_volume_service

router = APIRouter()


def _sse(gen: Iterator[dict]) -> StreamingResponse:
    def event_stream():
        for event in gen:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/volumes/{volume_id}", response_model=VolumeDetail)
def get_volume(
    volume_id: int,
    svc: VolumeService = Depends(get_volume_service),
):
    return svc.volume_detail(volume_id)


@router.post("/volumes/{volume_id}/outline", response_model=VolumeOut)
def generate_volume_outline(
    volume_id: int,
    svc: VolumeService = Depends(get_volume_service),
):
    return svc.generate_volume_outline(volume_id)


@router.put("/volumes/{volume_id}/outline", response_model=VolumeOut)
def save_volume_outline(
    volume_id: int,
    payload: ContentIn,
    svc: VolumeService = Depends(get_volume_service),
):
    return svc.save_volume_outline(volume_id, payload.content)


@router.post("/volumes/{volume_id}/chapter-plan", response_model=VolumeOut)
def generate_volume_plan(
    volume_id: int,
    svc: VolumeService = Depends(get_volume_service),
):
    return svc.generate_volume_plan(volume_id)


@router.put("/volumes/{volume_id}/chapter-plan", response_model=VolumeOut)
def save_volume_plan(
    volume_id: int,
    payload: ContentIn,
    svc: VolumeService = Depends(get_volume_service),
):
    return svc.save_volume_plan(volume_id, payload.content)


@router.post("/volumes/{volume_id}/chapters")
def generate_next_chapter(
    volume_id: int,
    svc: VolumeService = Depends(get_volume_service),
):
    svc.ensure_can_generate_chapter(volume_id)
    return _sse(svc.stream_next_chapter(volume_id))


@router.get("/volumes/{volume_id}/chapters", response_model=list[ChapterOut])
def list_volume_chapters(
    volume_id: int,
    svc: VolumeService = Depends(get_volume_service),
):
    return svc.list_volume_chapters(volume_id)


@router.get("/volumes/{volume_id}/export")
def export_volume(
    volume_id: int,
    svc: VolumeService = Depends(get_volume_service),
):
    return {"markdown": svc.export_volume(volume_id)}
