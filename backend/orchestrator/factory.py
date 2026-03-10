"""Engine factory -- assembles an OrchestrationEngine and manages its lifecycle."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from backend.agents.critic import CriticAgent
from backend.agents.director import DirectorAgent
from backend.agents.librarian import LibrarianAgent
from backend.agents.scientist import ScientistAgent
from backend.agents.subagent import SubAgentPool
from backend.agents.synthesizer import SynthesizerAgent
from backend.agents.writer import WriterAgent
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
from backend.models import Project, async_session_factory
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


async def _fetch_project_info(project_id: str) -> tuple[str, int]:
    """Fetch research_topic and concurrency from DB."""
    research_topic = ""
    concurrency = 1
    try:
        async with async_session_factory() as session:
            project = await session.get(Project, project_id)
            if project:
                research_topic = project.research_topic or ""
                concurrency = getattr(project, "concurrency", 1) or 1
    except Exception:
        logger.warning("Failed to fetch project info for %s", project_id)
    return research_topic, concurrency


async def _create_engine(
    project_id: str,
    *,
    workspace_path: Path | None = None,
    research_topic: str = "",
    lane_index: int | None = None,
) -> OrchestrationEngine:
    """Assemble all dependencies and return a ready-to-run engine.

    Args:
        project_id: The project UUID string.
        workspace_path: Override workspace path (used for lane workspaces).
        research_topic: Pre-fetched topic (avoids redundant DB queries for lanes).
        lane_index: If set, this engine is for a specific lane.
    """
    if workspace_path is None:
        workspace_path = settings.project_path(project_id)

    # Fetch research_topic from DB if not provided
    if not research_topic:
        research_topic, _ = await _fetch_project_info(project_id)

    lane_label = f" lane={lane_index}" if lane_index is not None else ""
    logger.info(
        "[Factory] project=%s%s research_topic=%r",
        project_id,
        lane_label,
        research_topic[:80],
    )

    llm_router = LLMRouter(tracker=TokenTracker(async_session_factory))
    action_executor = ActionExecutor()

    async def llm_call(messages: list[dict[str, str]]) -> str:
        resp = await llm_router.call(messages, model=_UTIL_MODEL)
        return resp.content

    level_gen = LevelGenerator(llm_call)
    board = Blackboard(workspace_path, action_executor=action_executor, level_generator=level_gen)
    await board.init_workspace(research_topic=research_topic)

    write_back_guard = WriteBackGuard(llm_call=llm_call)

    agents: dict[AgentRole, Any] = {
        AgentRole.DIRECTOR: DirectorAgent(
            llm_router,
            write_back_guard,
            research_topic=research_topic,
        ),
        AgentRole.SCIENTIST: ScientistAgent(
            llm_router,
            write_back_guard,
            research_topic=research_topic,
        ),
        AgentRole.LIBRARIAN: LibrarianAgent(
            llm_router,
            write_back_guard,
            research_topic=research_topic,
            project_id=str(project_id),
        ),
        AgentRole.WRITER: WriterAgent(
            llm_router,
            write_back_guard,
            research_topic=research_topic,
        ),
        AgentRole.CRITIC: CriticAgent(
            llm_router,
            write_back_guard,
            research_topic=research_topic,
        ),
        AgentRole.SYNTHESIZER: SynthesizerAgent(
            llm_router,
            write_back_guard,
            research_topic=research_topic,
        ),
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


# -----------------------------------------------------------------------
# Synthesis: aggregate lane artifacts and run synthesizer
# -----------------------------------------------------------------------


async def _collect_lane_artifacts(project_path: Path, num_lanes: int) -> str:
    """Read artifacts from all lane workspaces and build a combined context string."""
    sections: list[str] = []
    for lane_idx in range(num_lanes):
        lane_path = project_path / "lanes" / str(lane_idx)
        artifacts_dir = lane_path / "artifacts"
        if not artifacts_dir.exists():
            continue

        lane_parts: list[str] = [f"\n## Lane {lane_idx}\n"]
        for art_type_dir in sorted(artifacts_dir.iterdir()):
            if not art_type_dir.is_dir():
                continue
            for artifact_dir in sorted(art_type_dir.iterdir()):
                if not artifact_dir.is_dir():
                    continue
                meta_path = artifact_dir / "meta.json"
                if not meta_path.exists():
                    continue
                try:
                    meta = json.loads(meta_path.read_text())
                    if meta.get("superseded"):
                        continue
                    # Find latest version
                    versions = sorted(
                        [
                            d
                            for d in artifact_dir.iterdir()
                            if d.is_dir() and d.name.startswith("v")
                        ],
                        key=lambda d: int(d.name[1:]) if d.name[1:].isdigit() else 0,
                    )
                    if not versions:
                        continue
                    l2_file = versions[-1] / "l2.json"
                    if l2_file.exists():
                        content = l2_file.read_text()[:3000]
                        art_type = meta.get("artifact_type", art_type_dir.name)
                        lane_parts.append(
                            f"### {art_type} ({meta.get('artifact_id', '')})\n{content}\n"
                        )
                except Exception:
                    continue
        if len(lane_parts) > 1:  # has content beyond the header
            sections.append("\n".join(lane_parts))

    return "\n".join(sections) if sections else ""


async def _run_synthesis(
    project_id: str,
    project_path: Path,
    num_lanes: int,
    research_topic: str,
) -> None:
    """Run synthesis phase after all lanes complete."""
    broadcast = _build_ws_broadcast(project_id)
    await broadcast("SynthesisStarted", {"num_lanes": num_lanes})
    logger.info("[Factory] Starting synthesis for project %s (%d lanes)", project_id, num_lanes)

    # Collect artifacts from all lanes
    lane_context = await _collect_lane_artifacts(project_path, num_lanes)
    if not lane_context:
        logger.warning("[Factory] No lane artifacts found for synthesis")
        return

    # Create a synthesis engine that runs in the main project workspace
    # with the SYNTHESIZE phase as starting point
    synth_path = project_path  # synthesis writes to main project path
    engine = await _create_engine(
        project_id,
        workspace_path=synth_path,
        research_topic=research_topic,
    )

    # Inject lane context into the board's meta so the synthesizer can access it
    await engine._board.update_meta("phase", ResearchPhase.SYNTHESIZE.value)
    await engine._board.update_meta("lane_context", lane_context[:50000])
    await engine._board.update_meta("num_lanes", num_lanes)

    # Override the engine to start at SYNTHESIZE phase
    engine._phase = ResearchPhase.SYNTHESIZE
    engine._iteration = 0

    _running_engines[project_id] = engine
    try:
        await engine.run()
    finally:
        _running_engines.pop(project_id, None)

    logger.info("[Factory] Synthesis completed for project %s", project_id)


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------


async def start_engine(project_id: str) -> None:
    if project_id in _running_engines:
        logger.warning("Engine already running for project %s", project_id)
        return

    _stopped_projects.discard(project_id)

    research_topic, concurrency = await _fetch_project_info(project_id)
    logger.info(
        "Engine starting for project %s (concurrency=%d)...",
        project_id,
        concurrency,
    )

    async def _run_wrapper() -> None:
        restart_delay = 5
        try:
            while project_id not in _stopped_projects:
                try:
                    if concurrency <= 1:
                        # Single-lane: backward compatible, run directly
                        engine = await _create_engine(
                            project_id,
                            research_topic=research_topic,
                        )
                        _running_engines[project_id] = engine
                        logger.info("Engine run() starting for project %s", project_id)
                        await engine.run()
                    else:
                        # Multi-lane: run N engines concurrently, then synthesize
                        await _run_multi_lane(
                            project_id,
                            concurrency,
                            research_topic,
                        )

                    logger.info("Engine run() completed for project %s", project_id)
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
                        project_id,
                        restart_delay,
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


async def _run_multi_lane(
    project_id: str,
    num_lanes: int,
    research_topic: str,
) -> None:
    """Run N independent lane engines concurrently, then synthesize results."""
    project_path = settings.project_path(project_id)
    broadcast = _build_ws_broadcast(project_id)

    # Create lane workspaces and engines
    lane_engines: list[OrchestrationEngine] = []
    for lane_idx in range(num_lanes):
        lane_path = project_path / "lanes" / str(lane_idx)
        lane_path.mkdir(parents=True, exist_ok=True)
        (lane_path / "artifacts").mkdir(exist_ok=True)

        engine = await _create_engine(
            project_id,
            workspace_path=lane_path,
            research_topic=research_topic,
            lane_index=lane_idx,
        )
        lane_engines.append(engine)
        # Track the first lane engine as the "main" for is_running() checks
        if lane_idx == 0:
            _running_engines[project_id] = engine

    logger.info(
        "[Factory] Starting %d lane engines for project %s",
        num_lanes,
        project_id,
    )
    await broadcast(
        "LanesStarted",
        {"num_lanes": num_lanes, "project_id": project_id},
    )

    # Run all lanes concurrently -- COMPOSE is the final phase per lane
    # (SYNTHESIZE is skipped for individual lanes; it runs after all complete)
    async def _run_lane(idx: int, eng: OrchestrationEngine) -> None:
        try:
            logger.info("[Factory] Lane %d starting for project %s", idx, project_id)
            await eng.run()
            logger.info("[Factory] Lane %d completed for project %s", idx, project_id)
            await broadcast("LaneCompleted", {"lane": idx})
        except Exception:
            logger.exception("[Factory] Lane %d failed for project %s", idx, project_id)
            await broadcast("LaneCompleted", {"lane": idx, "error": True})

    await asyncio.gather(*[_run_lane(idx, eng) for idx, eng in enumerate(lane_engines)])

    # All lanes done -- run synthesis
    if project_id not in _stopped_projects:
        await _run_synthesis(project_id, project_path, num_lanes, research_topic)


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
