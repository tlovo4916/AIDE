from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import get_session, Project
from backend.orchestrator import factory as engine_factory
from backend.types import ResearchPhase

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    research_topic: str = ""
    config_json: dict | None = None


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    research_topic: str
    phase: str
    status: str
    config_json: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    body: ProjectCreate,
    session: AsyncSession = Depends(get_session),
) -> Project:
    project = Project(
        name=body.name,
        description=body.description,
        research_topic=body.research_topic,
        phase=ResearchPhase.EXPLORE.value,
        status="active",
        config_json=body.config_json,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)

    project_dir = settings.project_path(str(project.id))
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "papers").mkdir(exist_ok=True)
    (project_dir / "artifacts").mkdir(exist_ok=True)
    (project_dir / "logs").mkdir(exist_ok=True)

    return project


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    session: AsyncSession = Depends(get_session),
) -> list[Project]:
    result = await session.execute(select(Project).order_by(Project.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Project:
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    await session.delete(project)
    await session.commit()


@router.post("/{project_id}/start", response_model=ProjectOut)
async def start_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Project:
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if project.status not in ("active", "paused"):
        raise HTTPException(400, "Project cannot be started in current state")

    pid = str(project_id)
    if engine_factory.is_running(pid):
        raise HTTPException(409, "Research loop is already running")

    project.status = "running"
    await session.commit()
    await session.refresh(project)

    await engine_factory.start_engine(pid)

    return project


@router.post("/{project_id}/pause", response_model=ProjectOut)
async def pause_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Project:
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    pid = str(project_id)
    engine_factory.stop_engine(pid)

    project.status = "paused"
    await session.commit()
    await session.refresh(project)
    return project


@router.post("/{project_id}/resume", response_model=ProjectOut)
async def resume_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Project:
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if project.status != "paused":
        raise HTTPException(400, "Project is not paused")

    pid = str(project_id)
    if engine_factory.is_running(pid):
        raise HTTPException(409, "Research loop is already running")

    project.status = "running"
    await session.commit()
    await session.refresh(project)

    await engine_factory.start_engine(pid)

    return project
