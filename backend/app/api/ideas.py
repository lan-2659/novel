from fastapi import APIRouter, Depends

from ..schemas.entities import IdeaListOut, IdeaRequest
from ..services.idea_service import IdeaService
from .deps import get_idea_service

router = APIRouter()


@router.post("/ideas/generate", response_model=IdeaListOut)
def generate_ideas(
    payload: IdeaRequest,
    svc: IdeaService = Depends(get_idea_service),
):
    """随机生成多个小说创意灵感（不创建项目）。"""
    return {"ideas": svc.generate_ideas(payload.count, payload.genre, payload.style)}
