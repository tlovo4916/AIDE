"""Orchestrator planner -- LLM-based dynamic agent scheduling with rule fallback."""

from __future__ import annotations

import logging

from backend.config import settings
from backend.protocols import LLMRouter
from backend.types import (
    AgentRole,
    ArtifactType,
    ChallengeRecord,
    OrchestratorDecision,
    ResearchPhase,
    TaskPriority,
)
from backend.utils.json_utils import safe_json_loads

logger = logging.getLogger(__name__)

# Per-phase agent rotation sequence (fallback when LLM planner fails or is disabled)
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
    ResearchPhase.SYNTHESIZE: [
        AgentRole.SYNTHESIZER,
        AgentRole.CRITIC,
        AgentRole.SYNTHESIZER,
        AgentRole.CRITIC,
    ],
}

_PHASE_TASKS: dict[ResearchPhase, dict[AgentRole, str]] = {
    ResearchPhase.EXPLORE: {
        AgentRole.LIBRARIAN: (
            "Search and collect foundational literature on the"
            " research topic. Identify key papers, authors,"
            " methodologies, and open questions. If trend"
            " signals are available, prioritize searching for"
            " evidence on rising trends and emerging"
            " connections."
        ),
        AgentRole.DIRECTOR: (
            "Review gathered literature and set clear research"
            " directions. Define scope, key questions, and"
            " success criteria. If trend signals are"
            " available, incorporate rising trends and"
            " emerging connections into the research"
            " strategy."
        ),
        AgentRole.SCIENTIST: (
            "Analyze the collected evidence to identify"
            " patterns, gaps, and potential hypotheses worth"
            " investigating. Pay attention to any trend"
            " signals — rising trends may indicate promising"
            " research directions."
        ),
        AgentRole.CRITIC: (
            "Evaluate the current research state. Assess"
            " coverage of the topic, quality of sources, and"
            " identify gaps. Assign an overall score (1-10)."
        ),
    },
    ResearchPhase.HYPOTHESIZE: {
        AgentRole.SCIENTIST: (
            "Formulate specific, testable hypotheses based on"
            " the literature survey. Define variables,"
            " expected outcomes, and validation methods."
            " Leverage trend signals to identify hypotheses"
            " aligned with rising trends or emerging"
            " connections."
            " You MUST write artifacts with artifact_type='hypotheses'."
        ),
        AgentRole.DIRECTOR: (
            "Review and refine the proposed hypotheses."
            " Prioritize the most promising ones and set"
            " research strategy. Consider trend signals when"
            " prioritizing — hypotheses aligned with rising"
            " trends may have higher impact."
            " You MUST write artifacts with artifact_type='directions'."
        ),
        AgentRole.CRITIC: (
            "Evaluate the hypotheses for logical soundness,"
            " testability, and novelty. Assign an overall"
            " score (1-10)."
        ),
        AgentRole.LIBRARIAN: (
            "Search for additional evidence to support or challenge the proposed hypotheses."
            " You MUST write artifacts with artifact_type='evidence_findings'."
        ),
    },
    ResearchPhase.EVIDENCE: {
        AgentRole.LIBRARIAN: (
            "Conduct targeted literature search to gather"
            " evidence for the hypotheses. Focus on"
            " experimental data and empirical findings."
            " You MUST write artifacts with artifact_type='evidence_findings'."
        ),
        AgentRole.SCIENTIST: (
            "Analyze collected evidence and assess how well"
            " it supports or refutes the hypotheses."
            " Identify remaining gaps."
            " You MUST write artifacts with artifact_type='evidence_gaps' or 'experiment_guide'."
        ),
        AgentRole.CRITIC: (
            "Review the evidence quality, methodology rigor,"
            " and logical consistency. Assign an overall"
            " score (1-10)."
        ),
    },
    ResearchPhase.COMPOSE: {
        AgentRole.WRITER: (
            "Write or revise the research paper based on"
            " accumulated evidence and hypotheses. Include"
            " introduction, methods, results, discussion,"
            " and conclusion."
            " You MUST write artifacts with artifact_type='outline' or 'draft'."
        ),
        AgentRole.CRITIC: (
            "Review the draft for clarity, structure,"
            " argumentation, and academic rigor. Assign an"
            " overall score (1-10)."
        ),
    },
    ResearchPhase.COMPLETE: {
        AgentRole.CRITIC: (
            "Perform final quality review of the complete"
            " paper. Assign an overall score (1-10) and"
            " identify any remaining issues."
        ),
        AgentRole.WRITER: ("Address final reviewer comments and polish the paper for submission."),
    },
    ResearchPhase.SYNTHESIZE: {
        AgentRole.SYNTHESIZER: (
            "Synthesize findings from all research lanes"
            " into a unified paper. Compare hypotheses,"
            " weigh evidence quality (use critic scores),"
            " identify areas of agreement and"
            " contradiction, and produce a comprehensive"
            " synthesis."
        ),
        AgentRole.CRITIC: (
            "Review the synthesized paper for completeness,"
            " balanced integration of all lanes, and overall"
            " quality. Assign an overall score (1-10)."
        ),
    },
}

_AGENT_DESCRIPTIONS: dict[AgentRole, str] = {
    AgentRole.DIRECTOR: "制定研究方向和策略，协调各方工作",
    AgentRole.SCIENTIST: "提出假设，分析证据，识别研究空白",
    AgentRole.LIBRARIAN: "检索文献和证据，收集研究素材",
    AgentRole.WRITER: "撰写和修改论文草稿",
    AgentRole.CRITIC: "评估研究质量，打分并提出改进意见",
    AgentRole.SYNTHESIZER: "综合多条研究线索的发现",
}

# Mapping from artifact type to the agent role that produces it
_ARTIFACT_PRODUCER: dict[ArtifactType, AgentRole] = {
    ArtifactType.DIRECTIONS: AgentRole.DIRECTOR,
    ArtifactType.HYPOTHESES: AgentRole.SCIENTIST,
    ArtifactType.EVIDENCE_FINDINGS: AgentRole.LIBRARIAN,
    ArtifactType.EVIDENCE_GAPS: AgentRole.SCIENTIST,
    ArtifactType.EXPERIMENT_GUIDE: AgentRole.SCIENTIST,
    ArtifactType.OUTLINE: AgentRole.WRITER,
    ArtifactType.DRAFT: AgentRole.WRITER,
    ArtifactType.REVIEW: AgentRole.CRITIC,
    ArtifactType.TREND_SIGNALS: AgentRole.SCIENTIST,
}

_PLANNER_SYSTEM_PROMPT = (
    "你是研究协调员。根据当前研究阶段和黑板状态，选择下一个最合适的 Agent。\n"
    "输出严格 JSON 格式，不要输出其他内容。\n"
    'JSON schema: {"agent": "<role>", "task": "<任务描述>", '
    '"rationale": "<选择理由>"}'
)

# Critic must be invoked at least once every N iterations within a phase
_CRITIC_GUARANTEE_INTERVAL = 3


class OrchestratorPlanner:
    """Hybrid planner: LLM-based dynamic scheduling with rule-based fallback.

    When `enable_llm_planner` is True, the planner asks the LLM to choose
    the next agent based on the current board state. If the LLM call fails
    or returns an invalid agent, it falls back to the deterministic sequence.

    When `use_adaptive_planner` is True and a ResearchState is provided,
    the planner uses the DispatchScorer for deterministic state-aware
    scheduling, only falling back to LLM for tie-breaking.

    A Critic guarantee ensures the critic is invoked at least every
    _CRITIC_GUARANTEE_INTERVAL iterations regardless of LLM choice.
    """

    def __init__(
        self,
        llm_router: LLMRouter,
        research_topic: str = "",
        lane_perspective: str = "",
        event_bus: object | None = None,
        dispatch_scorer: object | None = None,
    ) -> None:
        self._llm_router = llm_router
        self._research_topic = research_topic
        self._lane_perspective = lane_perspective
        self._event_bus = event_bus
        self._dispatch_scorer = dispatch_scorer
        self._critic_last_iter: dict[str, int] = {}  # phase.value -> last iter critic was called
        # History buffer: phase.value -> list of (iteration, agent.value) tuples (last 5)
        self._selection_history: dict[str, list[tuple[int, str]]] = {}
        self._last_candidate_scores: list[dict] | None = None

    async def plan_next_action(
        self,
        board_state_summary: str,
        phase: ResearchPhase,
        iteration: int,
        open_challenges: list[ChallengeRecord] | None = None,
        missing_artifact_types: list[ArtifactType] | None = None,
        research_state: object | None = None,
    ) -> OrchestratorDecision:
        # Determine valid agents for this phase
        sequence = _PHASE_SEQUENCES.get(phase, [AgentRole.CRITIC])
        if settings.use_adaptive_planner and self._dispatch_scorer and research_state is not None:
            # Soft constraints: ALL agents are candidates; DispatchScorer applies
            # phase bonus/penalty so cross-phase agents can still win if need is high
            valid_agents = {
                AgentRole.LIBRARIAN, AgentRole.DIRECTOR, AgentRole.SCIENTIST,
                AgentRole.WRITER, AgentRole.CRITIC, AgentRole.SYNTHESIZER,
            }
        else:
            valid_agents = set(sequence)

        # Drain events from the event bus and enrich context
        event_notes: list[str] = []
        if self._event_bus is not None:
            try:
                events = await self._event_bus.drain()
                for ev in events:
                    for rel in ev.relations:
                        rel_type = rel.get("relation_type", "")
                        if rel_type == "contradicts":
                            event_notes.append(
                                f"Contradiction detected in {ev.artifact_type.value} "
                                f"artifact '{ev.artifact_id}' — Critic review recommended."
                            )
                        elif rel_type == "depends_on":
                            event_notes.append(
                                f"Dependency: {ev.artifact_type.value} '{ev.artifact_id}' "
                                f"depends on artifact {rel.get('target_id', 'unknown')}."
                            )
            except Exception:
                logger.debug("[Planner] Event bus drain failed (non-fatal)")

        # Critic guarantee: if critic hasn't run in _CRITIC_GUARANTEE_INTERVAL iters, force it
        last_critic = self._critic_last_iter.get(phase.value, 0)
        force_critic = (
            AgentRole.CRITIC in valid_agents
            and (iteration - last_critic) >= _CRITIC_GUARANTEE_INTERVAL
        )

        if force_critic:
            agent = AgentRole.CRITIC
            rationale = f"Critic guarantee: {iteration - last_critic} iterations since last critic"
            logger.info(
                "[Planner] Forcing CRITIC (last at iter %d, now %d)",
                last_critic,
                iteration,
            )
        elif settings.use_adaptive_planner and self._dispatch_scorer and research_state is not None:
            # Adaptive path: use DispatchScorer
            agent, rationale = await self._adaptive_select(
                board_state_summary,
                phase,
                iteration,
                valid_agents,
                research_state,
            )
        elif settings.enable_llm_planner:
            # Try LLM-based selection
            agent, rationale = await self._llm_select(
                board_state_summary,
                phase,
                iteration,
                valid_agents,
                open_challenges,
                missing_artifact_types,
            )
            if agent is None:
                # Fallback to rule-based
                agent, rationale = self._rule_select(
                    phase,
                    iteration,
                    missing_artifact_types,
                )
        else:
            agent, rationale = self._rule_select(
                phase,
                iteration,
                missing_artifact_types,
            )

        # Track critic invocations
        if agent == AgentRole.CRITIC:
            self._critic_last_iter[phase.value] = iteration

        # Challenge routing: if there are open challenges targeting an agent
        # in the valid set, prefer dispatching that agent
        if open_challenges and not force_critic:
            for ch in open_challenges:
                target = getattr(ch, "target_agent", None)
                if target and target in valid_agents and target != agent:
                    logger.info(
                        "[Planner] Overriding %s → %s due to open challenge %s",
                        agent.value,
                        target.value,
                        ch.challenge_id,
                    )
                    agent = target
                    rationale = (
                        f"Challenge routing: challenge {ch.challenge_id} targets {target.value}"
                    )
                    break

        # Build task description (adaptive or standard)
        if (
            settings.use_adaptive_planner
            and research_state is not None
            and hasattr(research_state, "missing_types")
        ):
            base_task = self._build_adaptive_task(agent, research_state, phase)
        else:
            task_map = _PHASE_TASKS.get(phase, {})
            base_task = task_map.get(
                agent, f"Perform your role duties for the {phase.value} phase."
            )

        task_desc = base_task

        if event_notes:
            task_desc += "\n\n" + "\n".join(f"⚠️ {note}" for note in event_notes)

        if self._lane_perspective:
            task_desc = f"[RESEARCH PERSPECTIVE]: {self._lane_perspective}\n\n{task_desc}"

        if missing_artifact_types:
            missing_lines = []
            for at in missing_artifact_types:
                producer = _ARTIFACT_PRODUCER.get(at)
                prod_str = f" (produced by {producer.value})" if producer else ""
                missing_lines.append(f"  - {at.value}{prod_str}")
            task_desc += (
                "\n\n⚠️ 以下 artifact 类型尚缺失，必须尽快产出:\n"
                + "\n".join(missing_lines)
                + "\n优先调度能产出缺失 artifact 的 Agent。"
            )

        allow_sub = agent in (AgentRole.LIBRARIAN, AgentRole.SCIENTIST)

        # Track selection history (keep last 5 per phase)
        hist = self._selection_history.setdefault(phase.value, [])
        hist.append((iteration, agent.value))
        if len(hist) > 5:
            self._selection_history[phase.value] = hist[-5:]

        logger.info(
            "[Planner] phase=%s iter=%d → agent=%s (%s)",
            phase.value,
            iteration,
            agent.value,
            rationale[:80],
        )

        # Collect candidate scores if available from adaptive path
        candidates = self._last_candidate_scores
        self._last_candidate_scores = None

        return OrchestratorDecision(
            agent_to_invoke=agent,
            task_description=task_desc,
            task_priority=TaskPriority.NORMAL,
            allow_subagents=allow_sub,
            trigger_checkpoint=False,
            rationale=rationale,
            candidate_scores=candidates,
        )

    async def _adaptive_select(
        self,
        board_state_summary: str,
        phase: ResearchPhase,
        iteration: int,
        valid_agents: set[AgentRole],
        research_state: object,
    ) -> tuple[AgentRole, str]:
        """Use DispatchScorer for state-aware agent selection.

        Falls back to LLM tie-breaker if top-2 scores are within threshold.
        """
        from backend.orchestrator.state_analyzer import ResearchState

        if not isinstance(research_state, ResearchState):
            # Fallback if wrong type
            return self._rule_select(phase, iteration, None)

        hist = self._selection_history.get(phase.value, [])
        scores = self._dispatch_scorer.score_agents(
            research_state, phase, valid_agents, selection_history=hist
        )
        if not scores:
            return self._rule_select(phase, iteration, None)

        # Store candidate scores for the engine to broadcast
        self._last_candidate_scores = [
            {"agent": s.role.value, "score": round(s.total, 3)} for s in scores
        ]

        top = scores[0]

        # Tie-breaker: if top 2 are within threshold, ask LLM
        if len(scores) >= 2:
            runner_up = scores[1]
            if (top.total - runner_up.total) < settings.adaptive_tie_threshold:
                logger.info(
                    "[Planner] Tie: %s(%.2f) vs %s(%.2f), asking LLM",
                    top.role.value,
                    top.total,
                    runner_up.role.value,
                    runner_up.total,
                )
                # Restrict LLM choice to the tied candidates
                tied = {top.role, runner_up.role}
                llm_agent, llm_rationale = await self._llm_select(
                    board_state_summary,
                    phase,
                    iteration,
                    tied,
                )
                if llm_agent is not None:
                    return llm_agent, f"Adaptive tie-break (LLM): {llm_rationale}"

        rationale = f"Adaptive: {top.role.value}={top.total:.2f} ({top.rationale[:80]})"
        return top.role, rationale

    def _build_adaptive_task(
        self,
        agent: AgentRole,
        research_state: object,
        phase: ResearchPhase,
    ) -> str:
        """Build a task description enriched with gap-specific instructions."""
        from backend.orchestrator.state_analyzer import ResearchState

        task_map = _PHASE_TASKS.get(phase, {})
        base = task_map.get(agent, f"Perform your role duties for the {phase.value} phase.")

        if not isinstance(research_state, ResearchState):
            return base

        extras: list[str] = []
        state = research_state

        if agent == AgentRole.LIBRARIAN and state.unsupported_hypothesis_count > 0:
            extras.append(
                f"⚠️ {state.unsupported_hypothesis_count} hypotheses lack supporting evidence. "
                "Prioritize finding evidence for existing hypotheses."
            )
        elif agent == AgentRole.SCIENTIST and state.hypothesis_count == 0:
            extras.append(
                "⚠️ No hypotheses exist yet. Focus on formulating initial hypotheses."
            )
        elif agent == AgentRole.DIRECTOR and state.iterations_without_progress > 3:
            extras.append(
                f"⚠️ Research has stagnated for {state.iterations_without_progress} iterations. "
                "Reassess strategy and identify new directions."
            )
        elif agent == AgentRole.WRITER:
            if not state.has_outline:
                extras.append("⚠️ No outline exists. Create a paper outline first.")
            elif not state.has_draft:
                extras.append("⚠️ Outline exists but no draft. Write the first draft.")
        elif agent == AgentRole.CRITIC and state.review_count == 0:
            extras.append(
                "⚠️ No reviews exist yet. Perform a comprehensive first review."
            )
        elif agent == AgentRole.SYNTHESIZER:
            if state.phase == ResearchPhase.SYNTHESIZE:
                extras.append(
                    "⚠️ Synthesis phase: integrate findings from all research lanes. "
                    "Compare hypotheses, weigh evidence quality, identify consensus "
                    "and contradictions across lanes."
                )
            if state.contradiction_count > 0:
                extras.append(
                    f"⚠️ {state.contradiction_count} contradictions detected. "
                    "Address conflicting evidence in your synthesis."
                )

        if state.missing_types:
            missing_str = ", ".join(at.value for at in state.missing_types[:5])
            extras.append(f"Missing artifacts for this phase: {missing_str}")

        if extras:
            return base + "\n\n" + "\n".join(extras)
        return base

    async def _llm_select(
        self,
        board_state_summary: str,
        phase: ResearchPhase,
        iteration: int,
        valid_agents: set[AgentRole],
        open_challenges: list[ChallengeRecord] | None = None,
        missing_artifact_types: list[ArtifactType] | None = None,
    ) -> tuple[AgentRole | None, str]:
        """Ask LLM to choose the next agent. Returns (agent, rationale) or (None, "") on failure."""
        agent_list = "\n".join(
            f"- {role.value}: {_AGENT_DESCRIPTIONS.get(role, '')}"
            for role in sorted(valid_agents, key=lambda r: r.value)
        )
        challenge_info = ""
        if open_challenges:
            ch_lines = []
            for ch in open_challenges[:3]:
                target = getattr(ch, "target_agent", None)
                target_str = f" (targets {target.value})" if target else ""
                ch_lines.append(f"  - [{ch.challenger.value}]{target_str}: {ch.argument[:100]}")
            challenge_info = "\n未解决的 Challenge:\n" + "\n".join(ch_lines)

        missing_info = ""
        if missing_artifact_types:
            missing_lines = []
            for at in missing_artifact_types:
                producer = _ARTIFACT_PRODUCER.get(at)
                prod_str = f" (produced by {producer.value})" if producer else ""
                missing_lines.append(f"  - {at.value}{prod_str}")
            missing_info = (
                "\n⚠️ 以下 artifact 类型尚缺失:\n"
                + "\n".join(missing_lines)
                + "\n请优先调度能产出缺失 artifact 的 Agent。\n"
            )

        # Build history info so planner avoids repeating the same agent
        history_info = ""
        hist = self._selection_history.get(phase.value, [])
        if hist:
            hist_lines = [f"  iter {it}: {ag}" for it, ag in hist]
            history_info = (
                "\n最近调度历史 (避免连续重复同一 Agent):\n" + "\n".join(hist_lines) + "\n"
            )

        prompt = (
            f"当前研究阶段: {phase.value}\n"
            f"迭代轮次: {iteration}\n"
            f"可用 Agent:\n{agent_list}\n"
            f"{challenge_info}{missing_info}{history_info}\n\n"
            f"<context>\n{board_state_summary[:3000]}\n</context>\n\n"
            f"请选择下一个要调度的 Agent，输出 JSON。"
        )

        try:
            raw = await self._llm_router.generate(
                settings.orchestrator_model,
                prompt,
                system_prompt=_PLANNER_SYSTEM_PROMPT,
                json_mode=True,
            )
            data = safe_json_loads(raw)
            if data is None:
                logger.warning("[Planner] LLM returned non-JSON: %s", raw[:200])
                return None, ""

            agent_str = data.get("agent", "")
            try:
                agent = AgentRole(agent_str)
            except ValueError:
                logger.warning("[Planner] LLM returned invalid agent: %r", agent_str)
                return None, ""

            if agent not in valid_agents:
                logger.warning(
                    "[Planner] LLM chose %s but not in valid set %s",
                    agent.value,
                    [a.value for a in valid_agents],
                )
                return None, ""

            rationale = f"LLM-planner: {data.get('rationale', '')[:120]}"
            return agent, rationale

        except Exception as exc:
            logger.warning("[Planner] LLM planner failed, falling back: %s", exc)
            return None, ""

    def _rule_select(
        self,
        phase: ResearchPhase,
        iteration: int,
        missing_artifact_types: list[ArtifactType] | None = None,
    ) -> tuple[AgentRole, str]:
        """Deterministic rule-based agent rotation (fallback).

        If missing_artifact_types is provided and the default agent cannot
        produce any of the missing types, override to the agent that can
        produce the first missing type.
        """
        sequence = _PHASE_SEQUENCES.get(phase, [AgentRole.CRITIC])
        agent = sequence[(iteration - 1) % len(sequence)]
        rationale = (
            f"Rule-based sequence: {phase.value}[{(iteration - 1) % len(sequence)}]={agent.value}"
        )

        if missing_artifact_types:
            # Check if current agent can produce any missing artifact
            can_produce = any(_ARTIFACT_PRODUCER.get(at) == agent for at in missing_artifact_types)
            if not can_produce:
                # Override to the agent that produces the first missing artifact
                for at in missing_artifact_types:
                    producer = _ARTIFACT_PRODUCER.get(at)
                    if producer and producer in set(sequence):
                        logger.info(
                            "[Planner] Coverage override: %s → %s for missing %s",
                            agent.value,
                            producer.value,
                            at.value,
                        )
                        rationale = f"Coverage override: {at.value} missing, need {producer.value}"
                        agent = producer
                        break

        return agent, rationale
