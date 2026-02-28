"""Director agent -- strategic research direction and conflict resolution."""

from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.types import AgentRole, ArtifactType


class DirectorAgent(BaseAgent):

    role = AgentRole.DIRECTOR
    system_prompt_template = "director.j2"
    preferred_model = "claude-opus-4-20250514"
    primary_artifact_types = [ArtifactType.DIRECTIONS]
    dependency_artifact_types = [
        ArtifactType.HYPOTHESES,
        ArtifactType.EVIDENCE_FINDINGS,
        ArtifactType.REVIEW,
    ]
    challengeable_roles: list[AgentRole] = []
    can_spawn_subagents = False
