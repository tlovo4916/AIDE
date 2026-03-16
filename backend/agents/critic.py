"""Critic agent -- quality review, consistency check, and scoring."""

from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.types import AgentRole, ArtifactType


class CriticAgent(BaseAgent):
    role = AgentRole.CRITIC
    system_prompt_template = "critic.j2"
    preferred_model = "deepseek-reasoner"
    primary_artifact_types = [ArtifactType.REVIEW]
    dependency_artifact_types = [
        ArtifactType.DIRECTIONS,
        ArtifactType.HYPOTHESES,
        ArtifactType.EVIDENCE_FINDINGS,
        ArtifactType.EVIDENCE_GAPS,
        ArtifactType.EXPERIMENT_GUIDE,
        ArtifactType.TREND_SIGNALS,
        ArtifactType.OUTLINE,
        ArtifactType.DRAFT,
    ]
    challengeable_roles = [
        AgentRole.DIRECTOR,
        AgentRole.SCIENTIST,
        AgentRole.LIBRARIAN,
        AgentRole.WRITER,
    ]
    can_spawn_subagents = False
