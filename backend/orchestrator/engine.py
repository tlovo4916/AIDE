"""Orchestration engine -- main spiral research loop."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Coroutine, Protocol

from backend.agents.base import BaseAgent
from backend.agents.subagent import SubAgentPool
from backend.orchestrator.backtrack import BacktrackController
from backend.orchestrator.convergence import ConvergenceDetector
from backend.orchestrator.heartbeat import HeartbeatMonitor
from backend.orchestrator.planner import OrchestratorPlanner
from backend.types import (
    AgentRole,
    AgentTask,
    BlackboardAction,
    ChallengeRecord,
    CheckpointAction,
    ContextLevel,
    OrchestratorDecision,
    ResearchPhase,
)

logger = logging.getLogger(__name__)

WSBroadcast = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]


class Board(Protocol):
    """Minimal blackboard interface expected by the orchestration engine."""

    async def get_state_summary(self, level: ContextLevel) -> str: ...
    async def apply_action(self, action: BlackboardAction) -> None: ...
    async def dedup_check(
        self, actions: list[BlackboardAction]
    ) -> list[BlackboardAction]: ...
    async def get_open_challenges(self) -> list[ChallengeRecord]: ...
    async def get_open_challenge_count(self) -> int: ...
    async def get_latest_critic_score(self) -> float: ...
    async def get_recent_revision_count(self, rounds: int) -> int: ...
    async def get_phase_iteration_count(
        self, phase: ResearchPhase
    ) -> int: ...
    async def get_artifacts_since_phase(
        self, phase: ResearchPhase
    ) -> list[str]: ...
    async def mark_superseded(self, artifact_id: str) -> None: ...
    async def update_meta(self, key: str, value: object) -> None: ...
    async def has_contradictory_evidence(self) -> bool: ...
    async def has_logic_gaps(self) -> bool: ...
    async def has_direction_issues(self) -> bool: ...
    async def serialize(self) -> dict[str, Any]: ...
    def get_project_path(self) -> Path: ...


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

    def __init__(self, board: Board) -> None:
        self._board = board

    async def build(self, role: AgentRole, task: str) -> str:
        return await self._board.get_state_summary(ContextLevel.L1)


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
    ) -> None:
        self._project_id = project_id
        self._board = board
        self._agents = agents
        self._planner = planner
        self._convergence = convergence
        self._backtrack = backtrack
        self._checkpoint_mgr = checkpoint_mgr
        self._heartbeat = heartbeat
        self._ws_broadcast = ws_broadcast
        self._subagent_pool: SubAgentPool | None = None

        self._running = False
        self._phase = ResearchPhase.EXPLORE
        self._iteration = 0

    def set_subagent_pool(self, pool: SubAgentPool) -> None:
        self._subagent_pool = pool

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        self._running = True
        logger.info("[Engine] Starting run loop for project %s", self._project_id)
        await self._heartbeat.start(self._project_id, self._board)

        try:
            while self._running and self._phase != ResearchPhase.COMPLETE:
                self._iteration += 1
                self._heartbeat.record_activity(self._project_id)
                logger.info(
                    "[Engine] === Iteration %d | phase=%s | project=%s ===",
                    self._iteration, self._phase.value, self._project_id,
                )

                # 1. Assess blackboard state
                logger.info("[Engine] Building state summary...")
                summary = await self._build_state_summary(self._board)
                logger.info("[Engine] State summary length: %d chars", len(summary))

                # 2. Plan next action
                logger.info("[Engine] Calling planner...")
                decision = await self._planner.plan_next_action(
                    summary, self._phase, self._iteration
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
                    await self._backtrack.execute_backtrack(
                        self._board, decision.backtrack_to
                    )
                    self._phase = decision.backtrack_to
                    await self._ws_broadcast(
                        "phase_change",
                        {
                            "project_id": self._project_id,
                            "phase": self._phase.value,
                            "reason": "backtrack",
                        },
                    )
                    continue

                # 5-6. Dispatch agent -> get actions
                actions = await self._dispatch_agent(decision)

                # 7. Dedup check
                actions = await self._board.dedup_check(actions)

                # Write validated actions to blackboard
                for action in actions:
                    await self._board.apply_action(action)

                await self._ws_broadcast(
                    "board_update",
                    {
                        "project_id": self._project_id,
                        "actions_count": len(actions),
                        "agent": decision.agent_to_invoke.value,
                        "phase": self._phase.value,
                        "iteration": self._iteration,
                    },
                )

                # 8. Handle challenges
                await self._handle_challenges(self._board)

                # 9. Convergence check
                signals = await self._convergence.check(
                    self._board, self._phase
                )

                backtrack_to = await self._backtrack.should_backtrack(
                    self._board, self._phase, signals
                )
                if backtrack_to:
                    await self._backtrack.execute_backtrack(
                        self._board, backtrack_to
                    )
                    self._phase = backtrack_to
                    await self._ws_broadcast(
                        "phase_change",
                        {
                            "project_id": self._project_id,
                            "phase": self._phase.value,
                            "reason": "auto_backtrack",
                        },
                    )
                elif signals.is_converged:
                    self._phase = await self._advance_phase(
                        self._board, self._phase
                    )

                logger.info(
                    "Iteration %d | phase=%s | converged=%s",
                    self._iteration,
                    self._phase.value,
                    signals.is_converged,
                )

        except Exception:
            logger.exception(
                "Orchestration loop failed at iteration %d", self._iteration
            )
            self._heartbeat.record_failure(self._project_id)
            raise
        finally:
            await self._heartbeat.stop(self._project_id)
            self._running = False

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------
    # Agent dispatch
    # ------------------------------------------------------------------

    async def _dispatch_agent(
        self, decision: OrchestratorDecision
    ) -> list[BlackboardAction]:
        agent = self._agents.get(decision.agent_to_invoke)
        if not agent:
            logger.error(
                "No agent registered for role %s",
                decision.agent_to_invoke.value,
            )
            return []

        self._heartbeat.record_agent_status(
            decision.agent_to_invoke.value, "executing"
        )

        task = AgentTask(
            task_id=(
                f"{self._project_id}-{self._iteration}"
                f"-{decision.agent_to_invoke.value}"
            ),
            description=decision.task_description,
            priority=decision.task_priority,
            allow_subagents=decision.allow_subagents,
        )

        context = await self._build_state_summary(self._board)
        response = await agent.execute(context, task)

        if response.subagent_requests and self._subagent_pool:
            workspace = self._board.get_project_path()
            ctx_builder = _BoardContextBuilder(self._board)
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
                    logger.warning(
                        "SubAgent %s failed: %s", sr.subagent_id, sr.error
                    )

        self._heartbeat.record_agent_status(
            decision.agent_to_invoke.value, "idle"
        )

        return response.actions

    # ------------------------------------------------------------------
    # Challenge handling
    # ------------------------------------------------------------------

    async def _handle_challenges(self, board: Board) -> bool:
        challenges = await board.get_open_challenges()
        if not challenges:
            return False

        for ch in challenges:
            await self._ws_broadcast(
                "challenge",
                {
                    "project_id": self._project_id,
                    "challenge_id": ch.challenge_id,
                    "challenger": ch.challenger.value,
                    "target_artifact": ch.target_artifact,
                    "argument": ch.argument,
                },
            )
        return True

    # ------------------------------------------------------------------
    # Phase management
    # ------------------------------------------------------------------

    async def _advance_phase(
        self, board: Board, current_phase: ResearchPhase
    ) -> ResearchPhase:
        next_phase = self._convergence.suggest_next_phase(current_phase)
        logger.info(
            "Phase transition: %s -> %s",
            current_phase.value,
            next_phase.value,
        )
        await self._ws_broadcast(
            "phase_change",
            {
                "project_id": self._project_id,
                "from_phase": current_phase.value,
                "to_phase": next_phase.value,
            },
        )
        return next_phase

    @staticmethod
    async def _build_state_summary(board: Board) -> str:
        return await board.get_state_summary(ContextLevel.L0)
