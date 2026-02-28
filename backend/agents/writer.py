"""Writer agent -- paper composition and revision."""

from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.types import AgentRole, ArtifactType


class WriterAgent(BaseAgent):

    role = AgentRole.WRITER
    system_prompt_template = "writer.j2"
    preferred_model = "openai/gpt-4o"
    primary_artifact_types = [
        ArtifactType.OUTLINE,
        ArtifactType.DRAFT,
    ]
    dependency_artifact_types = [
        ArtifactType.DIRECTIONS,
        ArtifactType.HYPOTHESES,
        ArtifactType.EVIDENCE_FINDINGS,
    ]
    challengeable_roles = [AgentRole.SCIENTIST]
    can_spawn_subagents = True
