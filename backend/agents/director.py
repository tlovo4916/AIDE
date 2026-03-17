"""Director agent -- strategic research direction and conflict resolution."""

from __future__ import annotations

import logging
import re

from backend.agents.base import BaseAgent
from backend.types import AgentResponse, AgentRole, AgentTask, ArtifactType

logger = logging.getLogger(__name__)


class DirectorAgent(BaseAgent):
    role = AgentRole.DIRECTOR
    system_prompt_template = "director.j2"
    preferred_model = "deepseek-reasoner"
    primary_artifact_types = [ArtifactType.DIRECTIONS]
    dependency_artifact_types = [
        ArtifactType.HYPOTHESES,
        ArtifactType.EVIDENCE_FINDINGS,
        ArtifactType.REVIEW,
    ]
    challengeable_roles: list[AgentRole] = []
    can_spawn_subagents = False

    async def pre_execute(self, context: str, task: AgentTask) -> str:
        """Build research map from board artifacts (not regex)."""
        lines: list[str] = []

        # Query board for actual artifacts
        if self._board:
            try:
                directions = await self._board.list_artifacts(ArtifactType.DIRECTIONS)
                hypotheses = await self._board.list_artifacts(ArtifactType.HYPOTHESES)
                evidence = await self._board.list_artifacts(ArtifactType.EVIDENCE_FINDINGS)
                reviews = await self._board.list_artifacts(ArtifactType.REVIEW)

                lines.append("\n## Research Map (from board)")
                lines.append(f"  Directions: {len(directions)} artifact(s)")
                lines.append(f"  Hypotheses: {len(hypotheses)} artifact(s)")
                lines.append(f"  Evidence: {len(evidence)} artifact(s)")
                lines.append(f"  Reviews: {len(reviews)} artifact(s)")

                # Extract RQs from direction artifacts
                rq_pattern = re.compile(
                    r"(?:RQ\d+|Research Question \d+|研究问题\s*\d+)[:\s]*(.*)",
                    re.I,
                )
                rq_list: list[str] = []
                for d in directions[-3:]:  # last 3 directions
                    text = d if isinstance(d, str) else str(d)
                    rq_list.extend(rq_pattern.findall(text))
                if rq_list:
                    lines.append("  Current Research Questions:")
                    for i, rq in enumerate(rq_list[:10], 1):
                        lines.append(f"    RQ{i}: {rq.strip()[:200]}")
            except Exception as exc:
                logger.debug("[Director] Board query failed: %s", exc)

        # Fallback: regex scan context if board unavailable or returned empty
        if len(lines) <= 1:
            rq_pattern = re.compile(
                r"(?:RQ\d+|Research Question \d+|研究问题\s*\d+)[:\s]*(.*)", re.I
            )
            rqs = rq_pattern.findall(context)
            if rqs:
                lines = ["\n## Research Map (from context)"]
                for i, rq in enumerate(rqs[:10], 1):
                    lines.append(f"  RQ{i}: {rq.strip()[:200]}")

        if lines:
            return context + "\n" + "\n".join(lines)
        return context

    async def post_execute(
        self, response: AgentResponse, context: str, task: AgentTask
    ) -> AgentResponse:
        """Validate output references existing RQs."""
        if not response.actions:
            return response

        for action in response.actions:
            content_text = str(action.content.get("text", ""))
            if action.target == ArtifactType.DIRECTIONS.value and content_text:
                has_rq_ref = bool(
                    re.search(r"(?:RQ\d+|research question|研究问题)", content_text, re.I)
                )
                if not has_rq_ref and len(content_text) > 100:
                    logger.info(
                        "[Director] Post-hook: directions output lacks RQ references"
                    )

        return response
