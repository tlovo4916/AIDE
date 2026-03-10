from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import Project, get_session
from backend.orchestrator import factory as engine_factory
from backend.types import ArtifactType, ResearchPhase

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    research_topic: str = ""
    concurrency: int = Field(default=1, ge=1, le=5)
    config_json: dict | None = None


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    research_topic: str
    concurrency: int = 1
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
        concurrency=body.concurrency,
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

    pid = str(project_id)
    # Stop running engine first
    engine_factory.stop_engine(pid)

    # Delete DB record
    await session.delete(project)
    await session.commit()

    # Delete filesystem workspace
    project_path = settings.project_path(pid)
    if project_path.exists():
        shutil.rmtree(project_path, ignore_errors=True)


@router.get("/{project_id}/blackboard")
async def get_blackboard(project_id: uuid.UUID) -> dict:
    """返回项目当前黑板快照（来自文件系统），用于前端页面刷新后恢复状态。"""
    project_path = settings.project_path(str(project_id))
    artifacts_dir = project_path / "artifacts"
    challenges_dir = project_path / "challenges"
    messages_dir = project_path / "messages"

    # 读取各类型 artifacts
    artifacts: dict[str, list] = {}
    if artifacts_dir.exists():
        for at in ArtifactType:
            type_dir = artifacts_dir / at.value
            if not type_dir.exists():
                continue
            items = []
            for artifact_dir in sorted(type_dir.iterdir()):
                if not artifact_dir.is_dir():
                    continue
                meta_path = artifact_dir / "meta.json"
                if not meta_path.exists():
                    continue
                try:
                    meta = json.loads(meta_path.read_text())
                    if meta.get("superseded"):
                        continue
                    # 读最新版本内容
                    versions = sorted(
                        [
                            d
                            for d in artifact_dir.iterdir()
                            if d.is_dir() and d.name.startswith("v")
                        ],
                        key=lambda d: int(d.name[1:]) if d.name[1:].isdigit() else 0,
                    )
                    content = ""
                    if versions:
                        l2 = versions[-1] / "l2.json"
                        if l2.exists():
                            content = l2.read_text()
                    items.append(
                        {
                            "id": meta.get("artifact_id", artifact_dir.name),
                            "type": at.value,
                            "data": {"content": content, **meta},
                        }
                    )
                except Exception:
                    continue
            if items:
                artifacts[at.value] = items

    # 读取 challenges
    challenges = []
    if challenges_dir.exists():
        for f in sorted(challenges_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                challenges.append(
                    {
                        "id": data.get("challenge_id", f.stem),
                        "from": data.get("challenger", ""),
                        "message": data.get("argument", ""),
                        "resolved": data.get("status", "") == "resolved",
                    }
                )
            except Exception:
                continue

    # 读取最近 messages（最多 50 条）
    messages = []
    if messages_dir.exists():
        msg_files = sorted(messages_dir.glob("*.json"))[-50:]
        for f in msg_files:
            try:
                data = json.loads(f.read_text())
                messages.append(
                    {
                        "id": data.get("message_id", f.stem),
                        "role": data.get("from_agent", ""),
                        "content": data.get("content", ""),
                        "timestamp": data.get("created_at", ""),
                    }
                )
            except Exception:
                continue

    return {"artifacts": artifacts, "challenges": challenges, "messages": messages}


@router.post("/{project_id}/start", response_model=ProjectOut)
async def start_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Project:
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    pid = str(project_id)
    # 允许 "running" 状态下引擎已死时重新启动
    dead_engine = project.status == "running" and not engine_factory.is_running(pid)
    if project.status not in ("active", "paused") and not dead_engine:
        raise HTTPException(400, "Project cannot be started in current state")

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
    pid = str(project_id)
    # 允许 "running" 状态下引擎已死时恢复
    dead_engine = project.status == "running" and not engine_factory.is_running(pid)
    if project.status != "paused" and not dead_engine:
        raise HTTPException(400, "Project is not paused")
    if engine_factory.is_running(pid):
        raise HTTPException(409, "Research loop is already running")

    project.status = "running"
    await session.commit()
    await session.refresh(project)

    await engine_factory.start_engine(pid)

    return project


@router.get("/{project_id}/export/paper")
async def get_exported_paper(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return exported paper content as JSON."""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    paper_path = settings.project_path(str(project_id)) / "exports" / "paper.md"
    if not paper_path.exists():
        raise HTTPException(404, "Paper not yet exported")

    content = paper_path.read_text(encoding="utf-8")
    return {"content": content, "filename": "paper.md"}


@router.get("/{project_id}/export/paper/download")
async def download_exported_paper(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Download exported paper as .md file."""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    paper_path = settings.project_path(str(project_id)) / "exports" / "paper.md"
    if not paper_path.exists():
        raise HTTPException(404, "Paper not yet exported")

    return FileResponse(
        path=str(paper_path),
        filename=f"{project.name}_paper.md",
        media_type="text/markdown",
    )
