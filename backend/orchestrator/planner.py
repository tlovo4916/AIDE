"""Orchestrator planner -- rule-based agent sequencing for reliable e2e flow."""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from backend.types import (
    AgentRole,
    OrchestratorDecision,
    ResearchPhase,
    TaskPriority,
)

logger = logging.getLogger(__name__)

# Per-phase agent rotation sequence (cycles when exhausted)
_PHASE_SEQUENCES: dict[ResearchPhase, list[AgentRole]] = {
    ResearchPhase.EXPLORE: [
        AgentRole.LIBRARIAN,
        AgentRole.DIRECTOR,
        AgentRole.LIBRARIAN,
        AgentRole.CRITIC,
    ],
    ResearchPhase.HYPOTHESIZE: [
        AgentRole.SCIENTIST,
        AgentRole.DIRECTOR,
        AgentRole.SCIENTIST,
        AgentRole.CRITIC,
    ],
    ResearchPhase.EVIDENCE: [
        AgentRole.LIBRARIAN,
        AgentRole.SCIENTIST,
        AgentRole.LIBRARIAN,
        AgentRole.CRITIC,
    ],
    ResearchPhase.COMPOSE: [
        AgentRole.WRITER,
        AgentRole.CRITIC,
        AgentRole.WRITER,
        AgentRole.CRITIC,
    ],
    ResearchPhase.COMPLETE: [
        AgentRole.CRITIC,
        AgentRole.WRITER,
        AgentRole.CRITIC,
        AgentRole.CRITIC,
    ],
}

_PHASE_TASKS: dict[ResearchPhase, dict[AgentRole, str]] = {
    ResearchPhase.EXPLORE: {
        AgentRole.LIBRARIAN: "Search and collect foundational literature on the research topic. Identify key papers, authors, methodologies, and open questions. If trend signals are available, prioritize searching for evidence on rising trends and emerging connections.",
        AgentRole.DIRECTOR: "Review gathered literature and set clear research directions. Define scope, key questions, and success criteria. If trend signals are available, incorporate rising trends and emerging connections into the research strategy.",
        AgentRole.SCIENTIST: "Analyze the collected evidence to identify patterns, gaps, and potential hypotheses worth investigating. Pay attention to any trend signals — rising trends may indicate promising research directions.",
        AgentRole.CRITIC: "Evaluate the current research state. Assess coverage of the topic, quality of sources, and identify gaps. Assign an overall score (1-10).",
    },
    ResearchPhase.HYPOTHESIZE: {
        AgentRole.SCIENTIST: "Formulate specific, testable hypotheses based on the literature survey. Define variables, expected outcomes, and validation methods. Leverage trend signals to identify hypotheses aligned with rising trends or emerging connections.",
        AgentRole.DIRECTOR: "Review and refine the proposed hypotheses. Prioritize the most promising ones and set research strategy. Consider trend signals when prioritizing — hypotheses aligned with rising trends may have higher impact.",
        AgentRole.CRITIC: "Evaluate the hypotheses for logical soundness, testability, and novelty. Assign an overall score (1-10).",
        AgentRole.LIBRARIAN: "Search for additional evidence to support or challenge the proposed hypotheses.",
    },
    ResearchPhase.EVIDENCE: {
        AgentRole.LIBRARIAN: "Conduct targeted literature search to gather evidence for the hypotheses. Focus on experimental data and empirical findings.",
        AgentRole.SCIENTIST: "Analyze collected evidence and assess how well it supports or refutes the hypotheses. Identify remaining gaps.",
        AgentRole.CRITIC: "Review the evidence quality, methodology rigor, and logical consistency. Assign an overall score (1-10).",
    },
    ResearchPhase.COMPOSE: {
        AgentRole.WRITER: "Write or revise the research paper based on accumulated evidence and hypotheses. Include introduction, methods, results, discussion, and conclusion.",
        AgentRole.CRITIC: "Review the draft for clarity, structure, argumentation, and academic rigor. Assign an overall score (1-10).",
    },
    ResearchPhase.COMPLETE: {
        AgentRole.CRITIC: "Perform final quality review of the complete paper. Assign an overall score (1-10) and identify any remaining issues.",
        AgentRole.WRITER: "Address final reviewer comments and polish the paper for submission.",
    },
}


@runtime_checkable
class LLMRouter(Protocol):
    async def generate(
        self, model: str, prompt: str, *, system_prompt: str | None = None
    ) -> str: ...


class OrchestratorPlanner:
    """Rule-based planner: deterministic agent rotation per research phase.

    Uses a predefined sequence per phase to guarantee diversity and ensure
    critic is invoked regularly (needed for score-based convergence).
    """

    def __init__(self, llm_router: LLMRouter, research_topic: str = "") -> None:
        # llm_router kept for interface compatibility but not used
        self._llm_router = llm_router
        self._research_topic = research_topic

    async def plan_next_action(
        self,
        board_state_summary: str,
        phase: ResearchPhase,
        iteration: int,
    ) -> OrchestratorDecision:
        sequence = _PHASE_SEQUENCES.get(phase, [AgentRole.CRITIC])
        # Use (iteration-1) so iteration=1 maps to sequence[0]
        agent = sequence[(iteration - 1) % len(sequence)]

        task_map = _PHASE_TASKS.get(phase, {})
        base_task = task_map.get(agent, f"Perform your role duties for the {phase.value} phase.")

        # Always prefix the task with the research topic so agents cannot drift
        if self._research_topic:
            task_desc = (
                f"[RESEARCH TOPIC]: {self._research_topic}\n\n"
                f"ALL your work MUST focus strictly on the above research topic.\n\n"
                f"{base_task}"
            )
        else:
            task_desc = base_task

        allow_sub = agent in (AgentRole.LIBRARIAN, AgentRole.SCIENTIST)

        logger.info(
            "[Planner] phase=%s iter=%d seq_pos=%d → agent=%s",
            phase.value, iteration, (iteration - 1) % len(sequence), agent.value,
        )

        return OrchestratorDecision(
            agent_to_invoke=agent,
            task_description=task_desc,
            task_priority=TaskPriority.NORMAL,
            allow_subagents=allow_sub,
            trigger_checkpoint=False,
            rationale=f"Rule-based sequence: {phase.value}[{(iteration-1) % len(sequence)}]={agent.value}",
        )
