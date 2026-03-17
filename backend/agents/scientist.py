"""Scientist agent -- hypothesis generation and methodology design."""

from __future__ import annotations

import logging
import re

from backend.agents.base import BaseAgent
from backend.types import (
    ActionType,
    AgentResponse,
    AgentRole,
    AgentTask,
    ArtifactType,
    BlackboardAction,
)

logger = logging.getLogger(__name__)


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

    async def pre_execute(self, context: str, task: AgentTask) -> str:
        """Build hypothesis registry from board artifacts."""
        lines: list[str] = []

        # Query board for actual hypothesis and evidence artifacts
        if self._board:
            try:
                hypotheses = await self._board.list_artifacts(ArtifactType.HYPOTHESES)
                evidence = await self._board.list_artifacts(ArtifactType.EVIDENCE_FINDINGS)

                if hypotheses:
                    lines.append("\n## Hypothesis Registry (from board)")
                    lines.append(f"  Total hypotheses: {len(hypotheses)}")
                    lines.append(f"  Total evidence: {len(evidence)}")

                    hyp_pattern = re.compile(
                        r"(?:H(\d+)|Hypothesis\s*(\d+)|假设\s*(\d+))[:\s]*(.*?)(?:\n|$)",
                        re.I,
                    )
                    for h in hypotheses[-5:]:  # last 5
                        text = h if isinstance(h, str) else str(h)
                        matches = hyp_pattern.findall(text)
                        for m in matches[:5]:
                            num = m[0] or m[1] or m[2]
                            desc = m[3].strip()[:200]
                            # Check evidence artifacts for support
                            ev_refs = 0
                            for e in evidence:
                                ev_text = e if isinstance(e, str) else str(e)
                                if f"H{num}" in ev_text or desc[:30] in ev_text:
                                    ev_refs += 1
                            status = "supported" if ev_refs > 0 else "unsupported"
                            lines.append(
                                f"  H{num}: [{status}] (evidence: {ev_refs}) {desc}"
                            )
            except Exception as exc:
                logger.debug("[Scientist] Board query failed: %s", exc)

        # Fallback: regex scan context
        if not lines:
            hyp_pattern = re.compile(
                r"(?:H(\d+)|Hypothesis\s*(\d+)|假设\s*(\d+))[:\s]*(.*?)(?:\n|$)", re.I
            )
            matches = hyp_pattern.findall(context)
            if matches:
                lines.append("\n## Hypothesis Registry (from context)")
                for m in matches[:15]:
                    num = m[0] or m[1] or m[2]
                    desc = m[3].strip()[:200]
                    lines.append(f"  H{num}: {desc}")

        if lines:
            return context + "\n" + "\n".join(lines)
        return context

    async def post_execute(
        self, response: AgentResponse, context: str, task: AgentTask
    ) -> AgentResponse:
        """Auto-raise challenge if hypotheses lack falsification criteria."""
        for action in response.actions:
            if action.target != ArtifactType.HYPOTHESES.value:
                continue
            content_text = str(action.content.get("text", ""))
            has_falsification = bool(
                re.search(
                    r"(?:falsif|refut|disprove|reject|反驳|证伪)",
                    content_text,
                    re.I,
                )
            )
            if not has_falsification and len(content_text) > 100:
                logger.info(
                    "[Scientist] Post-hook: raising challenge — "
                    "hypothesis missing falsification criteria"
                )
                response.actions.append(BlackboardAction(
                    agent_role=AgentRole.SCIENTIST.value,
                    action_type=ActionType.RAISE_CHALLENGE,
                    target=AgentRole.SCIENTIST.value,
                    content={
                        "argument": (
                            "Hypotheses lack falsification criteria. "
                            "Each hypothesis should specify conditions "
                            "under which it would be considered disproven."
                        ),
                    },
                ))
                break  # one challenge per response
        return response
