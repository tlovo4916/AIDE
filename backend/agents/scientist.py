"""Scientist agent -- hypothesis generation and methodology design."""

from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.types import AgentRole, ArtifactType


class ScientistAgent(BaseAgent):
    role = AgentRole.SCIENTIST
    system_prompt_template = "scientist.j2"
    preferred_model = "deepseek-reasoner"
    primary_artifact_types = [
        ArtifactType.HYPOTHESES,
        ArtifactType.EVIDENCE_GAPS,
        ArtifactType.EXPERIMENT_GUIDE,
    ]
    dependency_artifact_types = [
        ArtifactType.DIRECTIONS,
        ArtifactType.EVIDENCE_FINDINGS,
        ArtifactType.REVIEW,
    ]
    challengeable_roles = [AgentRole.DIRECTOR, AgentRole.LIBRARIAN]
    can_spawn_subagents = True
