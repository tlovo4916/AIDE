"""Canonical Protocol definitions for AIDE.

All modules should import Board and LLMRouter from here instead of
defining local copies.  Each Protocol is the *superset* of every
method required by any consumer in the codebase.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from backend.types import (
    AgentRole,
    ArtifactType,
    BlackboardAction,
    ChallengeRecord,
    ContextLevel,
    ResearchPhase,
)

# ---------------------------------------------------------------------------
# Board Protocol
# ---------------------------------------------------------------------------


class Board(Protocol):
    """Unified blackboard interface used by engine, convergence, backtrack,
    heartbeat, and subagent modules."""

    # -- State summary (engine, subagent, trend_extractor) ------------------

    async def get_state_summary(
        self,
        level: ContextLevel,
        relevant_types: set[ArtifactType] | None = None,
    ) -> str: ...

    # -- Artifact queries (engine, convergence) -----------------------------

    async def list_artifacts(
        self,
        artifact_type: ArtifactType,
        include_superseded: bool = False,
    ) -> list: ...

    # -- Action execution (engine) ------------------------------------------

    async def apply_action(self, action: BlackboardAction) -> None: ...

    async def dedup_check(
        self, actions: list[BlackboardAction]
    ) -> list[BlackboardAction]: ...

    # -- Challenge management (engine) --------------------------------------

    async def get_open_challenges(self) -> list[ChallengeRecord]: ...

    async def get_open_challenge_count(self) -> int: ...

    async def resolve_challenge(
        self, challenge_id: str, resolution: str
    ) -> None: ...

    # -- Critic / convergence scoring (engine, convergence) -----------------

    async def get_phase_critic_score(self, phase: ResearchPhase) -> float: ...

    async def set_phase_critic_score(
        self, phase: ResearchPhase, score: float
    ) -> None: ...

    async def get_recent_revision_count(self, rounds: int) -> int: ...

    async def get_phase_iteration_count(
        self, phase: ResearchPhase
    ) -> int: ...

    async def increment_phase_iteration(
        self, phase: ResearchPhase
    ) -> int: ...

    # -- Backtrack support (engine, backtrack) -------------------------------

    async def get_artifacts_since_phase(
        self, phase: ResearchPhase
    ) -> list[str]: ...

    async def mark_superseded(self, artifact_id: str) -> None: ...

    async def update_meta(self, key: str, value: object) -> None: ...

    async def get_project_meta(self) -> dict[str, Any]: ...

    async def has_contradictory_evidence(self) -> bool: ...

    async def has_logic_gaps(self) -> bool: ...

    async def has_direction_issues(self) -> bool: ...

    # -- Serialization / heartbeat (engine, heartbeat) ----------------------

    async def serialize(self) -> dict[str, Any]: ...

    def get_project_path(self) -> Path: ...

    # -- Export (engine) ----------------------------------------------------

    async def export_paper(self) -> Any: ...


# ---------------------------------------------------------------------------
# LLMRouter Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMRouter(Protocol):
    """Structural interface for the LLM routing layer.

    The superset includes parameters used by base agents (json_mode,
    project_id, agent_role), subagents, and trend_extractor.
    """

    async def generate(
        self,
        model: str,
        prompt: str,
        *,
        system_prompt: str | None = None,
        project_id: str | None = None,
        agent_role: AgentRole | None = None,
        json_mode: bool = False,
    ) -> str: ...

    def resolve_model(
        self, role: AgentRole | str | None = None
    ) -> str: ...
