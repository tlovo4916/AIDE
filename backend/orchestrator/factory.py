"""Engine factory -- assembles an OrchestrationEngine and manages its lifecycle."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.agents.director import DirectorAgent
from backend.agents.scientist import ScientistAgent
from backend.agents.librarian import LibrarianAgent
from backend.agents.writer import WriterAgent
from backend.agents.critic import CriticAgent
from backend.agents.subagent import SubAgentPool
from backend.api.ws import manager as ws_manager
from backend.blackboard.actions import ActionExecutor
from backend.blackboard.board import Blackboard
from backend.blackboard.levels import LevelGenerator
from backend.checkpoint.manager import CheckpointManager
from backend.config import settings
from backend.knowledge.trend_extractor import TrendExtractor
from backend.llm.router import LLMRouter
from backend.llm.tracker import TokenTracker
from backend.memory.write_back_guard import WriteBackGuard
from backend.models import async_session_factory, Project
from backend.orchestrator.backtrack import BacktrackController
from backend.orchestrator.convergence import ConvergenceDetector
from backend.orchestrator.engine import OrchestrationEngine
from backend.orchestrator.heartbeat import HeartbeatMonitor
from backend.orchestrator.planner import OrchestratorPlanner
from backend.types import AgentRole, CheckpointAction, ResearchPhase

logger = logging.getLogger(__name__)

_running_engines: dict[str, OrchestrationEngine] = {}
_running_tasks: dict[str, asyncio.Task[None]] = {}
_checkpoint_managers: dict[str, CheckpointManager] = {}
_stopped_projects: set[str] = set()  # explicitly stopped by user, no auto-restart


class _CheckpointBridge:
    """Adapts CheckpointManager to the Protocol expected by OrchestrationEngine."""

    def __init__(self, mgr: CheckpointManager) -> None:
        self._mgr = mgr

    async def trigger(
        self,
        project_id: str,
        phase: ResearchPhase,
        reason: str,
        summary: dict[str, Any],
    ) -> CheckpointAction:
        event = await self._mgr.create_checkpoint(project_id, phase, reason, summary)
        action, _ = await self._mgr.wait_for_response(
            event.checkpoint_id,
            timeout_minutes=settings.checkpoint_timeout_minutes,
        )
        return action


def _build_ws_broadcast(project_id: str):
    async def broadcast(event: str, payload: dict[str, Any]) -> None:
        await ws_manager.broadcast(project_id, event, payload)
    return broadcast


_UTIL_MODEL = "deepseek-chat"


async def _create_engine(project_id: str) -> OrchestrationEngine:
    """Assemble all dependencies and return a ready-to-run engine."""
    project_path = settings.project_path(project_id)

    # Fetch research_topic from DB so it can be injected into all components
    research_topic = ""
    try:
        async with async_session_factory() as session:
            project = await session.get(Project, project_id)
            if project:
                research_topic = project.research_topic or ""
    except Exception:
        logger.warning("Failed to fetch research_topic for project %s", project_id)
    logger.info("[Factory] project=%s research_topic=%r", project_id, research_topic[:80])

    llm_router = LLMRouter(tracker=TokenTracker(async_session_factory))
    action_executor = ActionExecutor()

    async def llm_call(messages: list[dict[str, str]]) -> str:
        resp = await llm_router.call(messages, model=_UTIL_MODEL)
        return resp.content

    level_gen = LevelGenerator(llm_call)
    board = Blackboard(project_path, action_executor=action_executor, level_generator=level_gen)
    await board.init_workspace(research_topic=research_topic)

    write_back_guard = WriteBackGuard(llm_call=llm_call)

    agents = {
        AgentRole.DIRECTOR: DirectorAgent(llm_router, write_back_guard, research_topic=research_topic),
        AgentRole.SCIENTIST: ScientistAgent(llm_router, write_back_guard, research_topic=research_topic),
        AgentRole.LIBRARIAN: LibrarianAgent(llm_router, write_back_guard, research_topic=research_topic, project_id=str(project_id)),
        AgentRole.WRITER: WriterAgent(llm_router, write_back_guard, research_topic=research_topic),
        AgentRole.CRITIC: CriticAgent(llm_router, write_back_guard, research_topic=research_topic),
    }

    planner = OrchestratorPlanner(llm_router, research_topic=research_topic)
    convergence = ConvergenceDetector()
    backtrack = BacktrackController()

    checkpoint_mgr = CheckpointManager(
        session_factory=async_session_factory,
        ws_broadcast=lambda payload: ws_manager.broadcast(
            project_id, payload.get("event_type", "checkpoint"), payload
        ),
    )
    _checkpoint_managers[project_id] = checkpoint_mgr
    checkpoint_bridge = _CheckpointBridge(checkpoint_mgr)
    heartbeat = HeartbeatMonitor()
    trend_extractor = TrendExtractor(llm_router)

    async def _on_phase_change(new_phase: str) -> None:
        try:
            async with async_session_factory() as session:
                project = await session.get(Project, project_id)
                if project:
                    project.phase = new_phase
                    await session.commit()
        except Exception:
            logger.warning("Failed to update DB phase for project %s", project_id)

    engine = OrchestrationEngine(
        project_id=project_id,
        board=board,
        agents=agents,
        planner=planner,
        convergence=convergence,
        backtrack=backtrack,
        checkpoint_mgr=checkpoint_bridge,
        heartbeat=heartbeat,
        ws_broadcast=_build_ws_broadcast(project_id),
        on_phase_change=_on_phase_change,
        trend_extractor=trend_extractor,
    )

    subagent_pool = SubAgentPool(llm_router)
    engine.set_subagent_pool(subagent_pool)

    return engine


async def _update_project_status(project_id: str, status: str) -> None:
    """Update project status in DB."""
    try:
        async with async_session_factory() as session:
            project = await session.get(Project, project_id)
            if project:
                project.status = status
                await session.commit()
    except Exception:
        logger.warning("Failed to update project %s status to %s", project_id, status)


async def start_engine(project_id: str) -> None:
    if project_id in _running_engines:
        logger.warning("Engine already running for project %s", project_id)
        return

    _stopped_projects.discard(project_id)
    logger.info("Engine created for project %s, starting run loop...", project_id)

    async def _run_wrapper() -> None:
        restart_delay = 5
        try:
            while project_id not in _stopped_projects:
                engine = await _create_engine(project_id)
                _running_engines[project_id] = engine
                try:
                    logger.info("Engine run() starting for project %s", project_id)
                    await engine.run()
                    logger.info("Engine run() completed for project %s", project_id)
                    # Normal completion — update DB status
                    await _update_project_status(project_id, "completed")
                    break
                except asyncio.CancelledError:
                    logger.info("Engine cancelled for project %s", project_id)
                    break
                except Exception:
                    if project_id in _stopped_projects:
                        break
                    logger.exception(
                        "Engine failed for project %s, restarting in %ds...",
                        project_id, restart_delay,
                    )
                    _running_engines.pop(project_id, None)
                    _checkpoint_managers.pop(project_id, None)
                    await asyncio.sleep(restart_delay)
                    restart_delay = min(restart_delay * 2, 60)
        finally:
            _running_engines.pop(project_id, None)
            _running_tasks.pop(project_id, None)
            _checkpoint_managers.pop(project_id, None)
            logger.info("Engine cleaned up for project %s", project_id)

    task = asyncio.create_task(_run_wrapper())
    _running_tasks[project_id] = task


def stop_engine(project_id: str) -> None:
    _stopped_projects.add(project_id)
    engine = _running_engines.get(project_id)
    if engine:
        engine.stop()


def get_engine(project_id: str) -> OrchestrationEngine | None:
    return _running_engines.get(project_id)


def is_running(project_id: str) -> bool:
    return project_id in _running_engines


def get_checkpoint_manager(project_id: str) -> CheckpointManager | None:
    return _checkpoint_managers.get(project_id)
