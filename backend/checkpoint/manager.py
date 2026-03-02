"""Checkpoint manager -- creates checkpoints and waits for user decisions."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.models.checkpoint import Checkpoint as CheckpointModel
from backend.types import CheckpointAction, CheckpointEvent, ResearchPhase

logger = logging.getLogger(__name__)


class CheckpointManager:

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        ws_broadcast: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._ws_broadcast = ws_broadcast
        self._pending: dict[str, asyncio.Event] = {}
        self._responses: dict[str, tuple[CheckpointAction, Optional[str]]] = {}
        self._meta: dict[str, dict[str, Any]] = {}

    async def create_checkpoint(
        self,
        project_id: str,
        phase: ResearchPhase,
        reason: str,
        summary: dict[str, Any],
    ) -> CheckpointEvent:
        checkpoint_id = str(uuid.uuid4())
        now = datetime.utcnow()

        async with self._session_factory() as session:
            row = CheckpointModel(
                id=uuid.UUID(checkpoint_id),
                project_id=uuid.UUID(project_id),
                phase=phase.value,
                reason=reason,
                summary_json=summary,
                created_at=now,
            )
            session.add(row)
            await session.commit()

        event = CheckpointEvent(
            checkpoint_id=checkpoint_id,
            project_id=project_id,
            phase=phase,
            reason=reason,
            summary=summary,
            created_at=now,
        )

        self._pending[checkpoint_id] = asyncio.Event()
        self._meta[checkpoint_id] = {
            "project_id": project_id,
            "phase": phase.value,
        }

        if self._ws_broadcast:
            await self._ws_broadcast({
                "event_type": "CheckpointCreated",
                "id": checkpoint_id,
                "project_id": project_id,
                "phase": phase.value,
                "summary": reason,
                "options": [
                    {"label": "Approve", "value": "approve"},
                    {"label": "Adjust", "value": "adjust"},
                    {"label": "Skip", "value": "skip"},
                ],
            })

        return event

    async def wait_for_response(
        self,
        checkpoint_id: str,
        timeout_minutes: int = 30,
    ) -> tuple[CheckpointAction, Optional[str]]:
        evt = self._pending.get(checkpoint_id)
        if evt is None:
            return CheckpointAction.SKIP, None

        try:
            await asyncio.wait_for(evt.wait(), timeout=timeout_minutes * 60)
        except asyncio.TimeoutError:
            logger.info("Checkpoint %s timed out, auto-skipping", checkpoint_id)
            self._responses.setdefault(
                checkpoint_id, (CheckpointAction.SKIP, None),
            )

        action, feedback = self._responses.pop(
            checkpoint_id, (CheckpointAction.SKIP, None),
        )
        self._pending.pop(checkpoint_id, None)

        meta = self._meta.pop(checkpoint_id, {})
        await self._persist_resolution(checkpoint_id, action, feedback)

        if self._ws_broadcast:
            await self._ws_broadcast({
                "event_type": "CheckpointResolved",
                "id": checkpoint_id,
                "project_id": meta.get("project_id", ""),
                "response": action.value,
            })

        return action, feedback

    async def apply_user_response(
        self,
        checkpoint_id: str,
        action: CheckpointAction,
        feedback: str | None = None,
    ) -> None:
        self._responses[checkpoint_id] = (action, feedback)
        evt = self._pending.get(checkpoint_id)
        if evt:
            evt.set()

    # ------------------------------------------------------------------

    async def _persist_resolution(
        self,
        checkpoint_id: str,
        action: CheckpointAction,
        feedback: str | None,
    ) -> None:
        try:
            async with self._session_factory() as session:
                stmt = (
                    update(CheckpointModel)
                    .where(CheckpointModel.id == uuid.UUID(checkpoint_id))
                    .values(
                        user_action=action.value,
                        user_feedback=feedback,
                        resolved_at=datetime.utcnow(),
                    )
                )
                await session.execute(stmt)
                await session.commit()
        except Exception as exc:
            logger.error("Failed to persist checkpoint resolution: %s", exc)
