"""Typed WebSocket push events for the checkpoint subsystem."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class WSPushEvent(BaseModel):
    project_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_type: str


class CheckpointCreatedEvent(WSPushEvent):
    event_type: str = "checkpoint.created"
    checkpoint_id: str
    phase: str
    reason: str
    summary: dict[str, Any] = Field(default_factory=dict)


class CheckpointResolvedEvent(WSPushEvent):
    event_type: str = "checkpoint.resolved"
    checkpoint_id: str
    action: str
    feedback: str = ""


class PhaseAdvancedEvent(WSPushEvent):
    event_type: str = "phase.advanced"
    from_phase: str
    to_phase: str
    reason: str = ""


class BacktrackEvent(WSPushEvent):
    event_type: str = "phase.backtrack"
    from_phase: str
    to_phase: str
    reason: str = ""


class AgentActivityEvent(WSPushEvent):
    event_type: str = "agent.activity"
    agent_role: str
    activity: str
    task_id: str = ""
    task_description: str = ""


class SubAgentSpawnedEvent(WSPushEvent):
    event_type: str = "subagent.spawned"
    subagent_id: str
    parent_role: str
    task: str = ""


class SubAgentCompletedEvent(WSPushEvent):
    event_type: str = "subagent.completed"
    subagent_id: str
    parent_role: str
    success: bool = True
    error: str | None = None


class ChallengeRaisedEvent(WSPushEvent):
    event_type: str = "challenge.raised"
    challenge_id: str
    challenger: str
    target_artifact: str
    argument: str = ""


class ChallengeResolvedEvent(WSPushEvent):
    event_type: str = "challenge.resolved"
    challenge_id: str
    responder: str
    status: str
    response: str = ""
