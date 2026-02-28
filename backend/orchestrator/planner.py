"""Orchestrator planner -- LLM-driven meta-cognitive decision making."""

from __future__ import annotations

import json
import logging
from typing import Protocol, runtime_checkable

from backend.types import (
    AgentRole,
    OrchestratorDecision,
    ResearchPhase,
)

logger = logging.getLogger(__name__)

_PLANNING_MODEL = "claude-opus-4-20250514"

_SYSTEM_PROMPT = """\
You are the meta-cognitive orchestrator of the AIDE multi-agent research system.

Your job is to observe the current state of the research blackboard and decide
which agent to invoke next, what task to assign, and whether strategic actions
(checkpoints, backtracking) are needed.

Available agents:
- director: Strategic research direction, conflict resolution
- scientist: Hypothesis generation, methodology design
- librarian: Literature search, evidence collection
- writer: Paper composition, revision
- critic: Quality review, scoring

Research phases (in order):
1. explore   -- initial literature survey and direction setting
2. hypothesize -- hypothesis formulation and refinement
3. evidence  -- evidence gathering and validation
4. compose   -- paper writing and revision
5. complete  -- final review and output

Decision guidelines:
- In early phases, favour librarian and director.
- When hypotheses exist but lack evidence, invoke librarian.
- Invoke critic periodically to assess quality.
- Trigger a checkpoint when a phase is about to transition, or when a
  strategic pivot is proposed.
- Suggest backtracking when contradictory evidence or fundamental direction
  problems are detected.

Respond with a JSON object:

{
    "agent_to_invoke": "director | scientist | librarian | writer | critic",
    "task_description": "Specific task for the agent",
    "task_priority": "critical | normal | exploratory",
    "allow_subagents": true,
    "trigger_checkpoint": false,
    "checkpoint_reason": null,
    "backtrack_to": null,
    "rationale": "Why this decision"
}
"""


@runtime_checkable
class LLMRouter(Protocol):
    async def generate(
        self, model: str, prompt: str, *, system_prompt: str | None = None
    ) -> str: ...


class OrchestratorPlanner:
    """Uses a high-capability LLM to make meta-cognitive scheduling decisions."""

    def __init__(self, llm_router: LLMRouter) -> None:
        self._llm_router = llm_router

    async def plan_next_action(
        self,
        board_state_summary: str,
        phase: ResearchPhase,
        iteration: int,
    ) -> OrchestratorDecision:
        prompt = self._build_prompt(board_state_summary, phase, iteration)
        raw = await self._llm_router.generate(
            _PLANNING_MODEL, prompt, system_prompt=_SYSTEM_PROMPT
        )
        return self._parse_decision(raw)

    # ------------------------------------------------------------------

    @staticmethod
    def _build_prompt(
        summary: str, phase: ResearchPhase, iteration: int
    ) -> str:
        return (
            f"## Research State\n\n"
            f"Phase: {phase.value}\n"
            f"Iteration: {iteration}\n\n"
            f"## Blackboard Summary (L0 Panoramic View)\n\n"
            f"{summary}\n\n"
            "Based on the current state, decide the next action.\n"
        )

    @staticmethod
    def _parse_decision(raw: str) -> OrchestratorDecision:
        text = raw.strip()
        for fence in ("```json", "```"):
            idx = text.find(fence)
            if idx == -1:
                continue
            start = idx + len(fence)
            end = text.find("```", start)
            if end == -1:
                continue
            text = text[start:end].strip()
            break

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning(
                "Planner returned non-JSON, falling back to critic review"
            )
            return OrchestratorDecision(
                agent_to_invoke=AgentRole.CRITIC,
                task_description="Review current research state and identify gaps",
                rationale="Fallback: could not parse planner output",
            )

        return OrchestratorDecision.model_validate(data)
