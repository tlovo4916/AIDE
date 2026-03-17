"""Synthesizer agent -- cross-lane research synthesis."""

from __future__ import annotations

import logging
import re

from backend.agents.base import BaseAgent
from backend.types import AgentResponse, AgentRole, AgentTask, ArtifactType

logger = logging.getLogger(__name__)


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

    async def pre_execute(self, context: str, task: AgentTask) -> str:
        """Build cross-lane comparison from board artifacts + context lanes."""
        lines: list[str] = []

        # Query board for artifact counts to build comparison
        hypotheses = await self._query_board(ArtifactType.HYPOTHESES)
        evidence = await self._query_board(ArtifactType.EVIDENCE_FINDINGS)
        reviews = await self._query_board(ArtifactType.REVIEW)
        drafts = await self._query_board(ArtifactType.DRAFT)

        if hypotheses or evidence or reviews or drafts:
            # Detect lane sections in context
            lane_pattern = re.compile(r"##\s*Lane\s*(\d+)", re.I)
            lane_ids = lane_pattern.findall(context)

            if len(lane_ids) >= 2:
                lines.append("\n## Cross-Lane Comparison Matrix (from board)")
                lines.append(f"  Lanes: {', '.join(lane_ids)}")
                lines.append(
                    f"  Total artifacts: {len(hypotheses)} hypotheses, "
                    f"{len(evidence)} evidence, {len(reviews)} reviews, "
                    f"{len(drafts)} drafts"
                )

                # Per-lane breakdown from context sections
                for lane_id in lane_ids[:5]:
                    lane_start = context.find(f"## Lane {lane_id}")
                    if lane_start < 0:
                        continue
                    next_lane = context.find("## Lane ", lane_start + 10)
                    lane_text = (
                        context[lane_start:next_lane]
                        if next_lane > 0
                        else context[lane_start:]
                    )
                    art_types = re.findall(r"###\s*(\w+)", lane_text)
                    lines.append(f"  Lane {lane_id}: {', '.join(art_types[:8])}")

        # Fallback: pure context-based lane detection
        if not lines:
            lane_pattern = re.compile(r"##\s*Lane\s*(\d+)", re.I)
            lane_ids = lane_pattern.findall(context)
            if len(lane_ids) >= 2:
                lines.append("\n## Cross-Lane Comparison (from context)")
                lines.append(f"  Lanes found: {', '.join(lane_ids)}")
                for lane_id in lane_ids[:5]:
                    lane_start = context.find(f"## Lane {lane_id}")
                    if lane_start < 0:
                        continue
                    next_lane = context.find("## Lane ", lane_start + 10)
                    lane_text = (
                        context[lane_start:next_lane]
                        if next_lane > 0
                        else context[lane_start:]
                    )
                    art_types = re.findall(r"###\s*(\w+)", lane_text)
                    lines.append(f"  Lane {lane_id}: {', '.join(art_types[:8])}")

        if lines:
            return context + "\n" + "\n".join(lines)
        return context

    async def post_execute(
        self, response: AgentResponse, context: str, task: AgentTask
    ) -> AgentResponse:
        """Warn if synthesis doesn't address disagreements between lanes."""
        for action in response.actions:
            if action.target != ArtifactType.DRAFT.value:
                continue
            content_text = str(action.content.get("text", ""))
            if len(content_text) < 200:
                continue

            has_disagreement_handling = bool(
                re.search(
                    r"(?:disagree|conflict|contradict|differ|discrepan|"
                    r"分歧|矛盾|不一致|差异)",
                    content_text,
                    re.I,
                )
            )
            lane_refs = len(re.findall(r"(?:lane\s*\d+|Lane\s*\d+)", content_text))

            if lane_refs >= 2 and not has_disagreement_handling:
                logger.info(
                    "[Synthesizer] Post-hook: synthesis references %d lanes "
                    "but doesn't address disagreements",
                    lane_refs,
                )

        return response
