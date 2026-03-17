"""In-memory event bus for artifact lifecycle events."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from backend.types import AgentRole, ArtifactType

logger = logging.getLogger(__name__)

_MAX_PENDING = 200


@dataclass
class ArtifactEvent:
    event_type: str  # "created" | "updated" | "challenged" | "superseded"
    artifact_type: ArtifactType
    artifact_id: str
    agent_role: AgentRole
    project_id: str
    relations: list[dict] = field(default_factory=list)


class EventBus:
    """Simple async event buffer. Producers call publish(); consumers call drain()."""

    def __init__(self) -> None:
        self._pending: list[ArtifactEvent] = []
        self._lock = asyncio.Lock()

    async def publish(self, event: ArtifactEvent) -> None:
        async with self._lock:
            self._pending.append(event)
            if len(self._pending) > _MAX_PENDING:
                self._pending = self._pending[-_MAX_PENDING:]

    async def drain(self) -> list[ArtifactEvent]:
        """Return and clear all pending events."""
        async with self._lock:
            events = list(self._pending)
            self._pending.clear()
            return events

    async def peek(self) -> list[ArtifactEvent]:
        """Return pending events without clearing."""
        async with self._lock:
            return list(self._pending)
