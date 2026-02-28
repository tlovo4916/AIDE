"""Write-back guard -- detects unpersisted insights in agent responses."""

from __future__ import annotations

import json
import logging
from typing import Awaitable, Callable

from backend.types import ActionType, AgentRole, BlackboardAction

logger = logging.getLogger(__name__)

LLMCall = Callable[[list[dict[str, str]]], Awaitable[str]]


class WriteBackGuard:

    def __init__(self, llm_call: LLMCall) -> None:
        self._llm_call = llm_call

    async def check(
        self,
        agent_response: str,
        executed_actions: list[BlackboardAction],
    ) -> list[BlackboardAction]:
        if not agent_response.strip():
            return []

        executed_summary = json.dumps(
            [
                {"type": a.action_type.value, "target": a.target}
                for a in executed_actions
            ],
            ensure_ascii=False,
        )

        prompt = (
            "Analyze the agent response below. Identify findings, conclusions, "
            "or insights NOT already captured by the executed actions.\n\n"
            f"Response:\n{agent_response}\n\n"
            f"Executed actions:\n{executed_summary}\n\n"
            "Return a JSON array of objects with keys: "
            '"content" (the unpersisted insight) and "refs" '
            "(list of referenced artifact IDs). "
            "Return [] if all insights are already captured."
        )

        try:
            result = await self._llm_call([
                {
                    "role": "system",
                    "content": (
                        "You identify unpersisted reasoning in agent outputs. "
                        "Respond with valid JSON array only."
                    ),
                },
                {"role": "user", "content": prompt},
            ])

            insights = json.loads(result.strip())
            if not isinstance(insights, list) or not insights:
                return []

            agent_role = (
                executed_actions[0].agent_role
                if executed_actions else AgentRole.DIRECTOR
            )

            additional: list[BlackboardAction] = []
            for item in insights:
                if not isinstance(item, dict) or not item.get("content"):
                    continue
                action = BlackboardAction(
                    agent_role=agent_role,
                    action_type=ActionType.POST_MESSAGE,
                    target="broadcast",
                    content={
                        "text": item["content"],
                        "refs": item.get("refs", []),
                        "source": "write_back_guard",
                    },
                )
                additional.append(action)

            return additional
        except Exception as exc:
            logger.warning("WriteBackGuard LLM check failed: %s", exc)
            return []
