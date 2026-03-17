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
        lines = await self._build_artifact_summary(
            [
                (ArtifactType.DIRECTIONS, "Directions"),
                (ArtifactType.HYPOTHESES, "Hypotheses"),
                (ArtifactType.EVIDENCE_FINDINGS, "Evidence"),
                (ArtifactType.REVIEW, "Reviews"),
            ],
            "Research Map",
        )

        if lines:
            # Extract RQs from direction artifacts
            directions = await self._query_board(ArtifactType.DIRECTIONS)
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

        # Fallback: regex scan context if board unavailable or returned empty
        if not lines:
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
