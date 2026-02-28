"""Librarian agent -- literature search, evidence collection, knowledge base."""

from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.types import AgentRole, ArtifactType


class LibrarianAgent(BaseAgent):

    role = AgentRole.LIBRARIAN
    system_prompt_template = "librarian.j2"
    preferred_model = "deepseek-reasoner"
    primary_artifact_types = [ArtifactType.EVIDENCE_FINDINGS]
    dependency_artifact_types = [
        ArtifactType.HYPOTHESES,
        ArtifactType.DIRECTIONS,
    ]
    challengeable_roles = [AgentRole.SCIENTIST]
    can_spawn_subagents = True
