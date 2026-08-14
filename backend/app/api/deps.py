from fastapi import Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..llm.deepseek_client import DeepSeekClient, LLMClient
from ..services.generation_service import GenerationService
from ..services.project_service import ProjectService


def get_llm_client() -> LLMClient:
    return DeepSeekClient()


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


def get_generation_service(
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
) -> GenerationService:
    return GenerationService(db, llm)
