"""Synthesizer agent -- cross-lane research synthesis."""

from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.types import AgentRole, ArtifactType


class SynthesizerAgent(BaseAgent):
    role = AgentRole.SYNTHESIZER
    system_prompt_template = "synthesizer.j2"
    preferred_model = "deepseek-reasoner"
    primary_artifact_types = [
        ArtifactType.DRAFT,
    ]
    dependency_artifact_types = [
        ArtifactType.HYPOTHESES,
        ArtifactType.EVIDENCE_FINDINGS,
        ArtifactType.DRAFT,
        ArtifactType.REVIEW,
    ]
    challengeable_roles = [AgentRole.SCIENTIST, AgentRole.WRITER]
    can_spawn_subagents = False
