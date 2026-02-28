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
from backend.checkpoint.manager import CheckpointManager
from backend.config import settings
from backend.llm.router import LLMRouter
from backend.llm.tracker import TokenTracker
from backend.memory.write_back_guard import WriteBackGuard
from backend.models import async_session_factory
from backend.orchestrator.backtrack import BacktrackController
from backend.orchestrator.convergence import ConvergenceDetector
from backend.orchestrator.engine import OrchestrationEngine
from backend.orchestrator.heartbeat import HeartbeatMonitor
from backend.orchestrator.planner import OrchestratorPlanner
from backend.types import AgentRole, CheckpointAction, ResearchPhase

logger = logging.getLogger(__name__)

_running_engines: dict[str, OrchestrationEngine] = {}
_running_tasks: dict[str, asyncio.Task[None]] = {}


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

    llm_router = LLMRouter(tracker=TokenTracker(async_session_factory))
    action_executor = ActionExecutor()
    board = Blackboard(project_path, action_executor=action_executor)
    await board.init_workspace()

    async def llm_call(messages: list[dict[str, str]]) -> str:
        resp = await llm_router.call(messages, model=_UTIL_MODEL)
        return resp.content

    write_back_guard = WriteBackGuard(llm_call=llm_call)

    agents = {
        AgentRole.DIRECTOR: DirectorAgent(llm_router, write_back_guard),
        AgentRole.SCIENTIST: ScientistAgent(llm_router, write_back_guard),
        AgentRole.LIBRARIAN: LibrarianAgent(llm_router, write_back_guard),
        AgentRole.WRITER: WriterAgent(llm_router, write_back_guard),
        AgentRole.CRITIC: CriticAgent(llm_router, write_back_guard),
    }

    planner = OrchestratorPlanner(llm_router)
    convergence = ConvergenceDetector()
    backtrack = BacktrackController()

    checkpoint_mgr = CheckpointManager(
        session_factory=async_session_factory,
        ws_broadcast=lambda payload: ws_manager.broadcast(
            project_id, payload.get("event_type", "checkpoint"), payload
        ),
    )
    checkpoint_bridge = _CheckpointBridge(checkpoint_mgr)
    heartbeat = HeartbeatMonitor()

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
    )

    subagent_pool = SubAgentPool(llm_router)
    engine.set_subagent_pool(subagent_pool)

    return engine


async def start_engine(project_id: str) -> None:
    if project_id in _running_engines:
        logger.warning("Engine already running for project %s", project_id)
        return

    engine = await _create_engine(project_id)

    _running_engines[project_id] = engine
    logger.info("Engine created for project %s, starting run loop...", project_id)

    async def _run_wrapper() -> None:
        try:
            logger.info("Engine run() starting for project %s", project_id)
            await engine.run()
            logger.info("Engine run() completed for project %s", project_id)
        except Exception:
            logger.exception("Engine failed for project %s", project_id)
        finally:
            _running_engines.pop(project_id, None)
            _running_tasks.pop(project_id, None)
            logger.info("Engine cleaned up for project %s", project_id)

    task = asyncio.create_task(_run_wrapper())
    _running_tasks[project_id] = task


def stop_engine(project_id: str) -> None:
    engine = _running_engines.get(project_id)
    if engine:
        engine.stop()


def get_engine(project_id: str) -> OrchestrationEngine | None:
    return _running_engines.get(project_id)


def is_running(project_id: str) -> bool:
    return project_id in _running_engines
