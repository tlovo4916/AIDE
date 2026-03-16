"""Write-back guard -- rule-based check for missing primary artifacts.

Verifies that an agent produced at least one artifact of its expected
primary types.  If none were found, generates a warning POST_MESSAGE
action so the gap is visible on the blackboard.

This replaces the previous LLM-based approach which had questionable ROI
(extra LLM call per agent invocation, many results filtered by dedup).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from backend.types import ActionType, AgentRole, ArtifactType, BlackboardAction

logger = logging.getLogger(__name__)

LLMCall = Callable[[list[dict[str, str]]], Awaitable[str]]

# Agent role -> expected primary artifact types
_ROLE_PRIMARY_TYPES: dict[AgentRole, set[str]] = {
    AgentRole.DIRECTOR: {"directions"},
    AgentRole.SCIENTIST: {"hypotheses", "evidence_gaps", "experiment_guide"},
    AgentRole.LIBRARIAN: {"evidence_findings", "trend_signals"},
    AgentRole.WRITER: {"outline", "draft"},
    AgentRole.CRITIC: {"review"},
    AgentRole.SYNTHESIZER: {"draft"},
}


class WriteBackGuard:
    def __init__(self, llm_call: LLMCall | None = None) -> None:
        # llm_call kept for interface compatibility but no longer used
        self._llm_call = llm_call

    async def check(
        self,
        agent_response: str,
        executed_actions: list[BlackboardAction],
    ) -> list[BlackboardAction]:
        """Check if the agent produced at least one primary artifact.

        Returns a warning POST_MESSAGE if no write_artifact action was found
        for any of the agent's expected primary types.
        """
        if not executed_actions:
            return []

        agent_role = executed_actions[0].agent_role
        expected = _ROLE_PRIMARY_TYPES.get(agent_role)
        if not expected:
            return []

        # Collect artifact types actually written
        written_types: set[str] = set()
        for action in executed_actions:
            if action.action_type == ActionType.WRITE_ARTIFACT:
                at = action.content.get("artifact_type", action.target)
                if isinstance(at, ArtifactType):
                    at = at.value
                written_types.add(at)

        if not written_types:
            # Agent produced no artifacts at all — emit a warning
            logger.info(
                "[WriteBackGuard] %s produced no artifacts (expected: %s)",
                agent_role.value,
                expected,
            )
            return [
                BlackboardAction(
                    agent_role=agent_role,
                    action_type=ActionType.POST_MESSAGE,
                    target="broadcast",
                    content={
                        "text": (
                            f"[WRITE-BACK WARNING] {agent_role.value} completed "
                            f"without producing any artifacts. "
                            f"Expected types: {', '.join(sorted(expected))}"
                        ),
                        "source": "write_back_guard",
                    },
                )
            ]

        # Check if any expected type was produced
        produced_expected = written_types & expected
        if not produced_expected:
            missing = expected - written_types
            logger.info(
                "[WriteBackGuard] %s wrote %s but expected %s",
                agent_role.value,
                written_types,
                expected,
            )
            return [
                BlackboardAction(
                    agent_role=agent_role,
                    action_type=ActionType.POST_MESSAGE,
                    target="broadcast",
                    content={
                        "text": (
                            f"[WRITE-BACK WARNING] {agent_role.value} wrote "
                            f"{', '.join(sorted(written_types))} but did not "
                            f"produce expected types: "
                            f"{', '.join(sorted(missing))}"
                        ),
                        "source": "write_back_guard",
                    },
                )
            ]

        return []
