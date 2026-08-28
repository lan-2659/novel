from fastapi import APIRouter, Depends

from ..schemas.entities import (
    ContentIn,
    ProjectCreate,
    ProjectDetail,
    ProjectOut,
    SettingOut,
    VolumeCreate,
    VolumeOut,
)
from ..services.generation_service import GenerationService
from ..services.project_service import ProjectService
from ..services.volume_service import VolumeService
from .deps import get_generation_service, get_project_service, get_volume_service

router = APIRouter()


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(
    payload: ProjectCreate,
    svc: ProjectService = Depends(get_project_service),
):
    return svc.create(payload.premise, payload.title)


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(svc: ProjectService = Depends(get_project_service)):
    return svc.list()


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_project(project_id: int, svc: ProjectService = Depends(get_project_service)):
    return svc.detail(project_id)


@router.post("/projects/{project_id}/settings", response_model=SettingOut)
def generate_setting(
    project_id: int,
    svc: GenerationService = Depends(get_generation_service),
):
    return svc.generate_setting(project_id)


@router.put("/projects/{project_id}/settings", response_model=SettingOut)
def save_setting(
    project_id: int,
    payload: ContentIn,
    svc: GenerationService = Depends(get_generation_service),
):
    return svc.save_setting(project_id, payload.content)


@router.post("/projects/{project_id}/outline", response_model=SettingOut)
def generate_outline(
    project_id: int,
    svc: GenerationService = Depends(get_generation_service),
):
    return svc.generate_outline(project_id)


@router.put("/projects/{project_id}/outline", response_model=SettingOut)
def save_outline(
    project_id: int,
    payload: ContentIn,
    svc: GenerationService = Depends(get_generation_service),
):
    return svc.save_outline(project_id, payload.content)


@router.post("/projects/{project_id}/volumes", response_model=VolumeOut, status_code=201)
def create_volume(
    project_id: int,
    payload: VolumeCreate,
    svc: VolumeService = Depends(get_volume_service),
):
    return svc.create_volume(project_id, payload.title)


@router.get("/projects/{project_id}/volumes", response_model=list[VolumeOut])
def list_volumes(
    project_id: int,
    svc: VolumeService = Depends(get_volume_service),
):
    return svc.list_volumes(project_id)


@router.get("/projects/{project_id}/export")
def export_project(
    project_id: int,
    svc: VolumeService = Depends(get_volume_service),
):
    return {"markdown": svc.export_project(project_id)}
