from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import get_session, Checkpoint
from backend.types import CheckpointAction

router = APIRouter(prefix="/projects/{project_id}/checkpoints", tags=["checkpoints"])


class CheckpointOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    phase: str
    reason: str
    summary_json: dict | None
    user_action: str | None
    user_feedback: str | None
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class CheckpointRespond(BaseModel):
    action: CheckpointAction
    feedback: str = ""


@router.get("", response_model=list[CheckpointOut])
async def list_checkpoints(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[Checkpoint]:
    result = await session.execute(
        select(Checkpoint)
        .where(Checkpoint.project_id == project_id)
        .order_by(Checkpoint.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{checkpoint_id}", response_model=CheckpointOut)
async def get_checkpoint(
    project_id: uuid.UUID,
    checkpoint_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Checkpoint:
    cp = await session.get(Checkpoint, checkpoint_id)
    if not cp or cp.project_id != project_id:
        raise HTTPException(404, "Checkpoint not found")
    return cp


@router.post("/{checkpoint_id}/respond", response_model=CheckpointOut)
async def respond_to_checkpoint(
    project_id: uuid.UUID,
    checkpoint_id: uuid.UUID,
    body: CheckpointRespond,
    session: AsyncSession = Depends(get_session),
) -> Checkpoint:
    cp = await session.get(Checkpoint, checkpoint_id)
    if not cp or cp.project_id != project_id:
        raise HTTPException(404, "Checkpoint not found")
    if cp.user_action is not None:
        raise HTTPException(400, "Checkpoint already resolved")

    cp.user_action = body.action.value
    cp.user_feedback = body.feedback or None
    cp.resolved_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(cp)

    # TODO: notify orchestrator of user decision

    return cp
