"""Orchestration engine -- main spiral research loop."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Coroutine
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from backend.agents.base import BaseAgent
from backend.agents.subagent import SubAgentPool
from backend.knowledge.trend_extractor import TrendExtractor
from backend.llm.tracker import TokenTracker
from backend.orchestrator.backtrack import BacktrackController
from backend.orchestrator.convergence import ConvergenceDetector, get_phase_required_artifacts
from backend.orchestrator.heartbeat import HeartbeatMonitor
from backend.orchestrator.planner import OrchestratorPlanner
from backend.types import (
    ActionType,
    AgentRole,
    AgentTask,
    ArtifactType,
    BlackboardAction,
    ChallengeRecord,
    CheckpointAction,
    ContextLevel,
    OrchestratorDecision,
    ResearchPhase,
)

# Auto-dismiss challenges that have been open longer than this many phase iterations
_CHALLENGE_AUTO_DISMISS_AFTER = 5

logger = logging.getLogger(__name__)

WSBroadcast = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]
PhaseChangeCallback = Callable[[str], Coroutine[Any, Any, None]]  # receives new phase value


class Board(Protocol):
    """Minimal blackboard interface expected by the orchestration engine."""

    async def get_state_summary(
        self,
        level: ContextLevel,
        relevant_types: set[ArtifactType] | None = None,
    ) -> str: ...
    async def list_artifacts(
        self, artifact_type: ArtifactType, include_superseded: bool = False
    ) -> list: ...
    async def apply_action(self, action: BlackboardAction) -> None: ...
    async def dedup_check(self, actions: list[BlackboardAction]) -> list[BlackboardAction]: ...
    async def get_open_challenges(self) -> list[ChallengeRecord]: ...
    async def get_open_challenge_count(self) -> int: ...
    async def get_phase_critic_score(self, phase: ResearchPhase) -> float: ...
    async def set_phase_critic_score(self, phase: ResearchPhase, score: float) -> None: ...
    async def get_recent_revision_count(self, rounds: int) -> int: ...
    async def get_phase_iteration_count(self, phase: ResearchPhase) -> int: ...
    async def increment_phase_iteration(self, phase: ResearchPhase) -> int: ...
    async def get_artifacts_since_phase(self, phase: ResearchPhase) -> list[str]: ...
    async def mark_superseded(self, artifact_id: str) -> None: ...
    async def update_meta(self, key: str, value: object) -> None: ...
    async def get_project_meta(self) -> dict[str, Any]: ...
    async def has_contradictory_evidence(self) -> bool: ...
    async def has_logic_gaps(self) -> bool: ...
    async def has_direction_issues(self) -> bool: ...
    async def serialize(self) -> dict[str, Any]: ...
    def get_project_path(self) -> Path: ...
    async def resolve_challenge(self, challenge_id: str, resolution: str) -> None: ...
    async def export_paper(self) -> Any: ...


class CheckpointManager(Protocol):
    async def trigger(
        self,
        project_id: str,
        phase: ResearchPhase,
        reason: str,
        summary: dict[str, Any],
    ) -> CheckpointAction: ...


class _BoardContextBuilder:
    """Adapts the Board into the ContextBuilder protocol for SubAgentPool."""

    def __init__(self, board: Board, agents: dict[AgentRole, BaseAgent] | None = None) -> None:
        self._board = board
        self._agents = agents

    async def build(self, role: AgentRole, task: str) -> str:
        relevant = _get_relevant_types(role, self._agents) if self._agents else None
        return await self._board.get_state_summary(ContextLevel.L1, relevant_types=relevant)


class OrchestrationEngine:
    """Drives the spiral research loop.

    Each iteration:
      1. Assess blackboard state (L0 panoramic view)
      2. Plan next action via LLM planner
      3. Optionally wait for user checkpoint
      4. Dispatch the chosen agent
      5. Execute agent (may spawn subagents)
      6. Write-back guard + results to blackboard
      7. Dedup check
      8. Handle new challenges
      9. Check convergence -> advance phase or backtrack
     10. Loop until COMPLETE

    Heartbeat runs concurrently for crash recovery.
    """

    def __init__(
        self,
        project_id: str,
        board: Board,
        agents: dict[AgentRole, BaseAgent],
        planner: OrchestratorPlanner,
        convergence: ConvergenceDetector,
        backtrack: BacktrackController,
        checkpoint_mgr: CheckpointManager,
        heartbeat: HeartbeatMonitor,
        ws_broadcast: WSBroadcast,
        on_phase_change: PhaseChangeCallback | None = None,
        trend_extractor: TrendExtractor | None = None,
        token_tracker: TokenTracker | None = None,
        lane_index: int | None = None,
        embedding_service: Any | None = None,
    ) -> None:
        self._project_id = project_id
        self._board = board
        self._agents = agents
        self._planner = planner
        self._convergence = convergence
        self._backtrack = backtrack
        self._checkpoint_mgr = checkpoint_mgr
        self._heartbeat = heartbeat
        self._raw_ws_broadcast = ws_broadcast
        self._on_phase_change = on_phase_change
        self._subagent_pool: SubAgentPool | None = None
        self._trend_extractor = trend_extractor
        self._token_tracker = token_tracker
        self._lane_index = lane_index
        self._embedding_service = embedding_service

        self._running = False
        self._phase = ResearchPhase.EXPLORE
        self._iteration = 0
        self._research_topic = ""
        self._skip_synthesize = True  # single-lane: COMPOSE→COMPLETE directly
        self._topic_embedding: list[float] | None = None
        self._topic_drift_detected = False  # set by _check_on_topic, read by _dispatch_agent

    async def _ws_broadcast(self, event: str, payload: dict[str, Any]) -> None:
        """Broadcast a WS event, automatically injecting lane_index if set."""
        if self._lane_index is not None:
            payload = {**payload, "lane_index": self._lane_index}
        await self._raw_ws_broadcast(event, payload)

    def set_subagent_pool(self, pool: SubAgentPool) -> None:
        self._subagent_pool = pool

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        self._running = True

        # Restore phase, iteration, and research_topic from persisted meta
        meta = await self._board.get_project_meta()
        saved_phase = meta.get("phase", ResearchPhase.EXPLORE.value)
        try:
            self._phase = ResearchPhase(saved_phase)
        except ValueError:
            self._phase = ResearchPhase.EXPLORE
        phase_iters = meta.get("phase_iterations", {})
        self._iteration = phase_iters.get(self._phase.value, 0)
        self._research_topic = meta.get("research_topic", "")

        logger.info(
            "[Engine] Starting run loop for project %s (restored phase=%s, iter_done=%d, topic=%r)",
            self._project_id,
            self._phase.value,
            self._iteration,
            self._research_topic[:60] if self._research_topic else "",
        )
        await self._heartbeat.start(self._project_id, self._board)

        # Inject lessons learned from previous projects
        await self._inject_lessons_learned()

        # Pre-compute topic embedding for semantic drift detection
        if self._embedding_service and self._research_topic and not self._topic_embedding:
            try:
                self._topic_embedding = await self._embedding_service.embed_text(
                    self._research_topic
                )
                logger.info(
                    "[Engine] Topic embedding computed (%d dims)",
                    len(self._topic_embedding),
                )
            except Exception:
                logger.warning("[Engine] Failed to compute topic embedding, using keyword fallback")

        try:
            while self._running and self._phase != ResearchPhase.COMPLETE:
                self._iteration += 1
                self._heartbeat.record_activity(self._project_id)
                await self._board.update_meta("iteration", self._iteration)
                await self._board.update_meta("phase", self._phase.value)
                logger.info(
                    "[Engine] === Iteration %d | phase=%s | project=%s ===",
                    self._iteration,
                    self._phase.value,
                    self._project_id,
                )

                # 1. Assess blackboard state (planner gets full panoramic view)
                logger.info("[Engine] Building state summary...")
                summary = await self._build_state_summary(self._board, role=None)
                logger.info("[Engine] State summary length: %d chars", len(summary))

                # 1b. Per-iteration on-topic check (log warning if research seems to drift)
                if self._research_topic and self._iteration > 1:
                    await self._check_on_topic(summary)

                # 2. Plan next action (compute missing artifacts for coverage loop)
                logger.info("[Engine] Calling planner...")
                open_challenges = await self._board.get_open_challenges()
                required = get_phase_required_artifacts(self._phase)
                missing: list[ArtifactType] = []
                for at in required:
                    arts = await self._board.list_artifacts(at)
                    if not arts:
                        missing.append(at)
                if missing:
                    logger.info(
                        "[Engine] Missing artifacts for %s: %s",
                        self._phase.value,
                        [at.value for at in missing],
                    )
                decision = await self._planner.plan_next_action(
                    summary, self._phase, self._iteration,
                    open_challenges=open_challenges or None,
                    missing_artifact_types=missing or None,
                )
                logger.info(
                    "[Engine] Planner decided: agent=%s, task=%s",
                    decision.agent_to_invoke.value,
                    decision.task_description[:100],
                )

                # 3. Checkpoint gate
                if decision.trigger_checkpoint:
                    user_action = await self._checkpoint_mgr.trigger(
                        self._project_id,
                        self._phase,
                        decision.checkpoint_reason or "Orchestrator checkpoint",
                        {
                            "iteration": self._iteration,
                            "summary": summary[:500],
                        },
                    )
                    if user_action == CheckpointAction.SKIP:
                        continue
                    # APPROVE -> proceed; ADJUST -> re-plan next iteration
                    if user_action == CheckpointAction.ADJUST:
                        continue

                # 4. Backtrack if requested
                if decision.backtrack_to:
                    prev_phase = self._phase
                    await self._backtrack.execute_backtrack(self._board, decision.backtrack_to)
                    self._phase = decision.backtrack_to
                    await self._ws_broadcast(
                        "Backtrack",
                        {
                            "from_phase": prev_phase.value,
                            "to_phase": self._phase.value,
                            "reason": "planned",
                        },
                    )
                    continue

                # 5. 通知前端 agent 已开始（立即反馈）
                await self._ws_broadcast(
                    "AgentStarted",
                    {
                        "agent": decision.agent_to_invoke.value,
                        "task": decision.task_description[:200],
                        "phase": self._phase.value,
                        "iteration": self._iteration,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

                # 6. Dispatch agent -> get actions (带总超时，防止 LLM 调用永久挂起)
                try:
                    actions = await asyncio.wait_for(self._dispatch_agent(decision), timeout=300.0)
                except TimeoutError:
                    logger.error(
                        "[Engine] Agent %s timed out after 300s on iteration %d",
                        decision.agent_to_invoke.value,
                        self._iteration,
                    )
                    await self._ws_broadcast(
                        "AgentError",
                        {
                            "agent": decision.agent_to_invoke.value,
                            "error": "Agent timed out after 300s",
                            "iteration": self._iteration,
                        },
                    )
                    # Still count the iteration to prevent infinite loops on repeated timeouts
                    await self._board.increment_phase_iteration(self._phase)
                    continue

                # 7. Dedup check
                actions = await self._board.dedup_check(actions)

                # Write validated actions to blackboard
                artifact_updates: list[dict[str, Any]] = []
                for action in actions:
                    try:
                        await self._board.apply_action(action)
                    except Exception as act_err:
                        logger.warning(
                            "[Engine] Skipping action %s from %s: %s",
                            action.action_type.value,
                            action.agent_role.value,
                            act_err,
                        )
                        continue
                    if action.action_type == ActionType.WRITE_ARTIFACT:
                        artifact_updates.append(
                            {
                                "artifact_type": action.content.get("artifact_type", action.target),
                                "artifact_id": action.content.get("artifact_id", ""),
                                "action": "created",
                                "data": action.content,
                            }
                        )
                        # Use agent_role instead of artifact_type string to
                        # reliably detect critic reviews (LLM often omits or
                        # mangles the artifact_type field).
                        if action.agent_role == AgentRole.CRITIC:
                            score = self._extract_critic_score(action.content)
                            if score is not None:
                                await self._board.set_phase_critic_score(self._phase, score)
                                logger.info(
                                    "[Engine] Phase %s critic score updated to %.1f",
                                    self._phase.value,
                                    score,
                                )

                await self._ws_broadcast(
                    "AgentActivity",
                    {
                        "agent": decision.agent_to_invoke.value,
                        "action": decision.task_description[:200],
                        "timestamp": datetime.utcnow().isoformat(),
                        "metadata": {
                            "iteration": self._iteration,
                            "actions": len(actions),
                            "phase": self._phase.value,
                        },
                    },
                )
                for upd in artifact_updates:
                    await self._ws_broadcast("ArtifactUpdated", upd)

                # 7b. Trend extraction
                await self._maybe_extract_trends()

                # 8. Handle challenges
                await self._handle_challenges(self._board)

                # 9. Convergence check
                await self._board.increment_phase_iteration(self._phase)
                signals = await self._convergence.check(self._board, self._phase)

                backtrack_to = await self._backtrack.should_backtrack(
                    self._board, self._phase, signals
                )
                if backtrack_to:
                    prev_phase = self._phase
                    await self._backtrack.execute_backtrack(self._board, backtrack_to)
                    self._phase = backtrack_to
                    await self._ws_broadcast(
                        "Backtrack",
                        {
                            "from_phase": prev_phase.value,
                            "to_phase": self._phase.value,
                            "reason": "auto",
                        },
                    )
                elif signals.is_converged:
                    self._phase = await self._advance_phase(self._board, self._phase)

                logger.info(
                    "Iteration %d | phase=%s | converged=%s",
                    self._iteration,
                    self._phase.value,
                    signals.is_converged,
                )

        except Exception:
            logger.exception("Orchestration loop failed at iteration %d", self._iteration)
            self._heartbeat.record_failure(self._project_id)
            raise
        finally:
            await self._heartbeat.stop(self._project_id)
            self._running = False

        # Normal completion: export paper and notify frontend
        if self._phase == ResearchPhase.COMPLETE:
            await self._on_research_complete()

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------
    # Agent dispatch
    # ------------------------------------------------------------------

    async def _dispatch_agent(self, decision: OrchestratorDecision) -> list[BlackboardAction]:
        agent = self._agents.get(decision.agent_to_invoke)
        if not agent:
            logger.error(
                "No agent registered for role %s",
                decision.agent_to_invoke.value,
            )
            return []

        self._heartbeat.record_agent_status(decision.agent_to_invoke.value, "executing")

        # Inject topic drift warning so the agent can self-correct
        task_desc = decision.task_description
        if self._topic_drift_detected and self._research_topic:
            task_desc += (
                f"\n\n[⚠️ TOPIC DRIFT WARNING] Recent output appears to be "
                f"drifting from the research topic: {self._research_topic[:200]}\n"
                f"Please ensure your output stays focused on this topic."
            )

        # Inject pending challenges targeted at this agent into the task description
        agent_challenges = [
            ch for ch in await self._board.get_open_challenges()
            if getattr(ch, "target_agent", None) == decision.agent_to_invoke
        ]
        if agent_challenges:
            ch_lines = [
                "\n\n[PENDING CHALLENGES — YOU MUST ADDRESS THESE]"
            ]
            for ch in agent_challenges[:3]:
                ch_lines.append(
                    f"Challenge from {ch.challenger.value}: {ch.argument[:300]}"
                )
            ch_lines.append(
                "You MUST include RESOLVE_CHALLENGE actions in your response "
                "to address these challenges."
            )
            task_desc += "\n".join(ch_lines)

        task = AgentTask(
            task_id=(f"{self._project_id}-{self._iteration}-{decision.agent_to_invoke.value}"),
            description=task_desc,
            priority=decision.task_priority,
            allow_subagents=decision.allow_subagents,
        )

        context = await self._build_state_summary(
            self._board, role=decision.agent_to_invoke,
        )
        response = await agent.execute(context, task)

        if response.subagent_requests and self._subagent_pool:
            workspace = self._board.get_project_path()
            ctx_builder = _BoardContextBuilder(self._board, self._agents)
            sub_results = await self._subagent_pool.spawn(
                agent.role,
                response.subagent_requests,
                workspace,
                ctx_builder,
                self._board,
            )
            for sr in sub_results:
                if sr.success:
                    logger.info("SubAgent %s completed: %s", sr.subagent_id, sr.task)
                else:
                    logger.warning("SubAgent %s failed: %s", sr.subagent_id, sr.error)

        self._heartbeat.record_agent_status(decision.agent_to_invoke.value, "idle")

        # Post-check: did the agent actually resolve its challenges?
        if agent_challenges:
            resolved_ids = {
                a.target
                for a in response.actions
                if a.action_type == ActionType.RESOLVE_CHALLENGE
            }
            unresolved = [
                ch for ch in agent_challenges if ch.challenge_id not in resolved_ids
            ]
            if unresolved:
                logger.warning(
                    "[Engine] %s had %d challenge(s) but resolved %d; "
                    "%d still open: %s",
                    decision.agent_to_invoke.value,
                    len(agent_challenges),
                    len(resolved_ids),
                    len(unresolved),
                    [ch.challenge_id for ch in unresolved],
                )

        return response.actions

    # ------------------------------------------------------------------
    # Research completion
    # ------------------------------------------------------------------

    async def _on_research_complete(self) -> None:
        """Clean up open challenges, export paper, report token usage, and notify frontend."""
        try:
            remaining = await self._board.get_open_challenges()
            for ch in remaining:
                await self._board.resolve_challenge(
                    ch.challenge_id,
                    "Auto-dismissed: research completed.",
                )
                logger.info(
                    "[Engine] Dismissed leftover challenge %s on completion",
                    ch.challenge_id,
                )

            paper_path = await self._board.export_paper()

            # Collect token usage summary
            token_usage: dict[str, Any] | None = None
            if self._token_tracker:
                try:
                    token_usage = await self._token_tracker.get_project_usage(self._project_id)
                    logger.info(
                        "[Engine] Token usage: %d tokens, $%.4f USD / %.4f RMB, %d calls",
                        token_usage.get("total_tokens", 0),
                        token_usage.get("total_cost_usd", 0),
                        token_usage.get("total_cost_rmb", 0),
                        token_usage.get("total_calls", 0),
                    )
                except Exception:
                    logger.exception("[Engine] Failed to collect token usage")

            await self._ws_broadcast(
                "ResearchCompleted",
                {
                    "phase": ResearchPhase.COMPLETE.value,
                    "paper_path": str(paper_path) if paper_path else None,
                    "token_usage": token_usage,
                },
            )
            logger.info("[Engine] Research completed. Paper at %s", paper_path)

            # Generate lessons learned for cross-project knowledge
            await self._generate_lessons_learned()
        except Exception:
            logger.exception("[Engine] Error during research completion export")

    async def _generate_lessons_learned(self) -> None:
        """Generate and persist lessons learned from this research project."""
        try:
            from backend.config import settings as cfg

            summary = await self._build_state_summary(self._board, role=None)
            summary_truncated = summary[:3000]

            prompt = (
                "Based on this completed research project, extract lessons learned.\n"
                f"Research topic: {self._research_topic}\n\n"
                f"Project summary:\n{summary_truncated}\n\n"
                "Output JSON with keys: strategies (list of effective strategies), "
                "pitfalls (list of pitfalls to avoid), "
                "insights (list of key insights for future research).\n"
                "Output raw JSON only."
            )

            raw = await self._planner._llm_router.generate(
                cfg.orchestrator_model, prompt, json_mode=True,
            )
            from backend.utils.json_utils import safe_json_loads

            lessons = safe_json_loads(raw)
            if not lessons:
                logger.warning("[Engine] Lessons learned: LLM returned non-JSON")
                return

            lessons_dir = (
                cfg.workspace_dir / "global_knowledge" / "lessons"
            )
            lessons_dir.mkdir(parents=True, exist_ok=True)
            lessons_path = lessons_dir / f"{self._project_id}.json"
            lessons_path.write_text(json.dumps(lessons, ensure_ascii=False, indent=2))
            logger.info("[Engine] Lessons learned saved to %s", lessons_path)
        except Exception:
            logger.exception("[Engine] Failed to generate lessons learned (non-fatal)")

    async def _inject_lessons_learned(self) -> None:
        """Load lessons from previous projects and inject into board meta."""
        try:
            from backend.config import settings as cfg

            lessons_dir = cfg.workspace_dir / "global_knowledge" / "lessons"
            if not lessons_dir.exists():
                return

            all_lessons: list[dict] = []
            for path in sorted(lessons_dir.glob("*.json"))[-5:]:
                if path.stem == self._project_id:
                    continue  # skip own project
                try:
                    data = json.loads(path.read_text())
                    if isinstance(data, dict):
                        all_lessons.append(data)
                except Exception:
                    continue

            if not all_lessons:
                return

            # Merge into concise summary
            strategies: list[str] = []
            pitfalls: list[str] = []
            for lesson in all_lessons:
                for s in lesson.get("strategies", [])[:3]:
                    if isinstance(s, str) and s not in strategies:
                        strategies.append(s)
                for p in lesson.get("pitfalls", [])[:3]:
                    if isinstance(p, str) and p not in pitfalls:
                        pitfalls.append(p)

            if strategies or pitfalls:
                summary = ""
                if strategies:
                    summary += "Effective strategies: " + "; ".join(strategies[:5])
                if pitfalls:
                    summary += "\nPitfalls to avoid: " + "; ".join(pitfalls[:5])
                await self._board.update_meta(
                    "lessons_learned", summary[:2000],
                )
                logger.info(
                    "[Engine] Injected lessons from %d previous projects",
                    len(all_lessons),
                )
        except Exception:
            logger.debug("[Engine] Lessons injection failed (non-fatal)")

    # ------------------------------------------------------------------
    # Challenge handling
    # ------------------------------------------------------------------

    async def _handle_challenges(self, board: Board) -> bool:
        challenges = await board.get_open_challenges()
        if not challenges:
            return False

        phase_iters = await board.get_phase_iteration_count(self._phase)

        for ch in challenges:
            await self._ws_broadcast(
                "ChallengeRaised",
                {
                    "id": ch.challenge_id,
                    "from": ch.challenger.value,
                    "target": ch.target_artifact,
                    "message": ch.argument,
                },
            )
            # Auto-dismiss challenges that agents have not responded to after
            # _CHALLENGE_AUTO_DISMISS_AFTER iterations — prevents permanent
            # convergence deadlock.
            if phase_iters > _CHALLENGE_AUTO_DISMISS_AFTER:
                logger.info(
                    "[Engine] Auto-dismissing challenge %s after %d iterations",
                    ch.challenge_id,
                    phase_iters,
                )
                await board.resolve_challenge(
                    ch.challenge_id,
                    f"Auto-dismissed: no agent response after {phase_iters} iterations.",
                )
                await self._ws_broadcast(
                    "ChallengeResolved",
                    {
                        "id": ch.challenge_id,
                        "resolution": "auto-dismissed",
                    },
                )
        return True

    # ------------------------------------------------------------------
    # Trend extraction
    # ------------------------------------------------------------------

    async def _maybe_extract_trends(self) -> None:
        """Extract trend signals every N iterations during EXPLORE/EVIDENCE phases."""
        from backend.config import settings as cfg
        from backend.types import ArtifactType as ArtType

        if not self._trend_extractor or not cfg.enable_trend_extraction:
            return
        if self._phase not in (ResearchPhase.EXPLORE, ResearchPhase.EVIDENCE):
            return
        if self._iteration % cfg.trend_extraction_interval != 0:
            return

        logger.info("[Engine] Running trend extraction at iteration %d", self._iteration)
        try:
            result = await self._trend_extractor.process_evidence_artifacts(self._board)
            if not result:
                return

            import json

            action = BlackboardAction(
                agent_role=AgentRole.SCIENTIST,
                action_type=ActionType.WRITE_ARTIFACT,
                target="trend_signals",
                content={
                    "artifact_type": ArtType.TREND_SIGNALS.value,
                    "text": json.dumps(result, ensure_ascii=False),
                    "trends": result.get("trends", []),
                    "entities": result.get("entities", []),
                    "summary": result.get("summary", ""),
                },
                rationale="Automated trend signal extraction from evidence",
                context_level=ContextLevel.L1,
            )
            await self._board.apply_action(action)
            await self._ws_broadcast(
                "ArtifactUpdated",
                {
                    "artifact_type": ArtType.TREND_SIGNALS.value,
                    "artifact_id": f"trends-iter-{self._iteration}",
                    "action": "created",
                    "data": result,
                },
            )
            logger.info(
                "[Engine] Trend signals extracted: %d trends, %d entities",
                len(result.get("trends", [])),
                len(result.get("entities", [])),
            )
        except Exception:
            logger.exception("[Engine] Trend extraction failed")

    # ------------------------------------------------------------------
    # Phase management
    # ------------------------------------------------------------------

    async def _advance_phase(self, board: Board, current_phase: ResearchPhase) -> ResearchPhase:
        next_phase = self._convergence.suggest_next_phase(current_phase)
        # Single-lane engines skip SYNTHESIZE (goes COMPOSE → COMPLETE directly)
        if next_phase == ResearchPhase.SYNTHESIZE and self._skip_synthesize:
            next_phase = ResearchPhase.COMPLETE
        logger.info(
            "Phase transition: %s -> %s",
            current_phase.value,
            next_phase.value,
        )
        # Persist the new phase immediately so crash-restart restores correctly
        await board.update_meta("phase", next_phase.value)
        await self._ws_broadcast(
            "PhaseAdvanced",
            {
                "from_phase": current_phase.value,
                "phase": next_phase.value,
            },
        )
        if self._on_phase_change:
            await self._on_phase_change(next_phase.value)
        return next_phase

    async def _check_on_topic(self, summary: str) -> None:
        """Warn via WS if the state summary appears to be off the research topic.

        Three-layer fallback:
          1. Embedding cosine similarity (if embedding_service available)
          2. jieba segmentation (for Chinese topics)
          3. Whitespace keyword matching (final fallback)
        """
        from backend.config import settings as cfg

        if not self._research_topic:
            return

        match_ratio: float | None = None
        method = "unknown"
        on_topic = True
        threshold = 0.5

        # Layer 1: Embedding similarity
        if self._topic_embedding and self._embedding_service:
            try:
                summary_emb = await self._embedding_service.embed_text(summary[:2000])
                sim = self._cosine_similarity(self._topic_embedding, summary_emb)
                match_ratio = sim
                method = "embedding"
                threshold = cfg.topic_drift_embedding_threshold
                on_topic = sim >= threshold
            except Exception:
                logger.debug("[Engine] Embedding drift check failed, trying jieba")

        # Layer 2: jieba segmentation (better for Chinese)
        if match_ratio is None:
            try:
                import jieba
                topic_words = set(jieba.cut(self._research_topic))
                topic_words = {w for w in topic_words if len(w) > 1}
                if topic_words:
                    summary_lower = summary[:5000].lower()
                    matched = sum(1 for w in topic_words if w.lower() in summary_lower)
                    match_ratio = matched / len(topic_words)
                    method = "jieba"
                    threshold = cfg.topic_drift_keyword_threshold
                    on_topic = match_ratio >= threshold
            except ImportError:
                logger.debug("[Engine] jieba not available, using whitespace fallback")

        # Layer 3: Whitespace keyword matching (final fallback)
        if match_ratio is None:
            topic_words_ws = set(self._research_topic.lower().split())
            topic_words_ws = {w for w in topic_words_ws if len(w) > 2}
            if not topic_words_ws:
                return
            summary_lower = summary.lower()
            matched = sum(1 for w in topic_words_ws if w in summary_lower)
            match_ratio = matched / len(topic_words_ws)
            method = "keyword"
            threshold = cfg.topic_drift_keyword_threshold
            on_topic = match_ratio >= threshold

        if match_ratio is None:
            return

        if not on_topic:
            self._topic_drift_detected = True
            logger.warning(
                "[Engine] ON-TOPIC CHECK FAILED (%s) at iteration %d: "
                "score=%.2f (threshold=%.2f). "
                "Research may have drifted from: %r",
                method, self._iteration, match_ratio, threshold,
                self._research_topic[:80],
            )
            await self._ws_broadcast(
                "TopicDriftWarning",
                {
                    "iteration": self._iteration,
                    "research_topic": self._research_topic,
                    "match_ratio": round(match_ratio, 2),
                    "method": method,
                    "message": (
                        f"Research may be drifting from the intended topic: "
                        f"{self._research_topic[:100]}"
                    ),
                },
            )
        else:
            self._topic_drift_detected = False
            logger.debug(
                "[Engine] On-topic check passed (%s, score=%.2f)",
                method, match_ratio,
            )

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        import math

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _extract_critic_score(content: dict[str, Any]) -> float | None:
        """Extract numeric score from review action content.

        Handles multiple structures the LLM may produce:
          1. {"score": 8, ...}  -- top-level
          2. {"content": '{"score": 8, ...}', ...}  -- nested JSON string
          3. {"content_l2": '{"score": 8, ...}', ...}
          4. {"text": '{"score": 8, ...}'}  -- wrapped by _parse_response
        """
        import json as _json

        for key in ("score", "overall_score"):
            val = content.get(key)
            if isinstance(val, (int, float)):
                return float(val)

        for field in ("content", "content_l2", "text"):
            raw = content.get(field)
            if isinstance(raw, dict):
                # Nested dict (not JSON string) — scan directly
                for key in ("score", "overall_score"):
                    val = raw.get(key)
                    if isinstance(val, (int, float)):
                        return float(val)
                continue
            if not isinstance(raw, str):
                continue
            try:
                parsed = _json.loads(raw)
                if isinstance(parsed, dict):
                    for key in ("score", "overall_score"):
                        val = parsed.get(key)
                        if isinstance(val, (int, float)):
                            return float(val)
            except (ValueError, TypeError):
                continue
        return None

    async def _build_state_summary(
        self, board: Board, role: AgentRole | None = None,
    ) -> str:
        from backend.blackboard.context_builder import build_budget_context

        relevant = _get_relevant_types(role, self._agents) if role else None
        return await build_budget_context(board, relevant_types=relevant)


def _get_relevant_types(
    role: AgentRole | None,
    agents: dict[AgentRole, BaseAgent] | None,
) -> set[ArtifactType] | None:
    """Return the set of artifact types an agent role should see, or None for all."""
    if role is None or agents is None:
        return None
    agent = agents.get(role)
    if agent is None:
        return None
    types: set[ArtifactType] = set()
    types.update(agent.primary_artifact_types)
    types.update(agent.dependency_artifact_types)
    return types if types else None
