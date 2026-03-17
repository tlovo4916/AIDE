"""Engine factory -- assembles an OrchestrationEngine and manages its lifecycle."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import aiofiles

from backend.agents.critic import CriticAgent
from backend.agents.director import DirectorAgent
from backend.agents.librarian import LibrarianAgent
from backend.agents.scientist import ScientistAgent
from backend.agents.subagent import SubAgentPool
from backend.agents.synthesizer import SynthesizerAgent
from backend.agents.write_back_guard import WriteBackGuard
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

_LANE_PERSPECTIVES: list[str] = [
    "Focus on theoretical foundations and formal analysis",
    "Focus on practical applications and empirical results",
    "Focus on limitations, criticisms, and alternative approaches",
    "Focus on interdisciplinary connections and emerging trends",
    "Focus on methodological innovations and reproducibility",
]


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


async def _fetch_project_info(
    project_id: str,
) -> tuple[str, int, dict | None]:
    """Fetch research_topic, concurrency, and config_json from DB."""
    research_topic = ""
    concurrency = 1
    config_json: dict | None = None
    try:
        async with async_session_factory() as session:
            project = await session.get(Project, project_id)
            if project:
                research_topic = project.research_topic or ""
                concurrency = getattr(project, "concurrency", 1) or 1
                config_json = getattr(project, "config_json", None)
    except Exception:
        logger.warning("Failed to fetch project info for %s", project_id)
    return research_topic, concurrency, config_json


async def _create_engine(
    project_id: str,
    *,
    workspace_path: Path | None = None,
    research_topic: str = "",
    lane_index: int | None = None,
    lane_perspective: str = "",
    model_overrides: dict[str, str] | None = None,
    embedding_model: str | None = None,
) -> OrchestrationEngine:
    """Assemble all dependencies and return a ready-to-run engine.

    Args:
        project_id: The project UUID string.
        workspace_path: Override workspace path (used for lane workspaces).
        research_topic: Pre-fetched topic (avoids redundant DB queries for lanes).
        lane_index: If set, this engine is for a specific lane.
        model_overrides: Per-project/per-lane agent model overrides (from config_json).
        embedding_model: Per-project embedding model override (from config_json).
    """
    if workspace_path is None:
        workspace_path = settings.project_path(project_id)

    # Fetch research_topic from DB if not provided
    if not research_topic:
        research_topic, _, _ = await _fetch_project_info(project_id)

    lane_label = f" lane={lane_index}" if lane_index is not None else ""
    logger.info(
        "[Factory] project=%s%s research_topic=%r overrides=%s",
        project_id,
        lane_label,
        research_topic[:80],
        list(model_overrides.keys()) if model_overrides else "global",
    )

    token_tracker = TokenTracker(async_session_factory)
    llm_router = LLMRouter(tracker=token_tracker, agent_model_overrides=model_overrides)
    action_executor = ActionExecutor()

    async def llm_call(messages: list[dict[str, str]]) -> str:
        resp = await llm_router.call(messages, model=_UTIL_MODEL)
        return resp.content

    level_gen = LevelGenerator(llm_call)

    # Embedding service (used by both SemanticBoard and drift detection)
    embedding_service = None
    if settings.openrouter_api_key:
        try:
            from backend.knowledge.embeddings import EmbeddingService

            embedding_service = EmbeddingService(model=embedding_model)
        except Exception:
            logger.warning("[Factory] Failed to create EmbeddingService")

    # Board: SemanticBoard (feature flag) or filesystem Blackboard
    event_bus = None
    if settings.use_semantic_board:
        from backend.blackboard.event_bus import EventBus
        from backend.blackboard.semantic_board import SemanticBoard

        event_bus = EventBus()
        board = SemanticBoard(
            project_path=workspace_path,
            session_factory=async_session_factory,
            embedding_service=embedding_service,
            llm_router=llm_router,
            project_id=project_id,
            event_bus=event_bus,
            action_executor=action_executor,
            level_generator=level_gen,
        )
    else:
        board = Blackboard(
            workspace_path, action_executor=action_executor, level_generator=level_gen
        )

    await board.init_workspace(research_topic=research_topic)

    write_back_guard = WriteBackGuard(llm_call=llm_call)

    # Phase 4: Adaptive planner components (feature-flagged)
    state_analyzer = None
    dispatch_scorer = None
    info_service = None
    if settings.use_adaptive_planner:
        from backend.orchestrator.dispatch_scorer import DispatchScorer
        from backend.orchestrator.info_request_service import InfoRequestService
        from backend.orchestrator.state_analyzer import ResearchStateAnalyzer

        state_analyzer = ResearchStateAnalyzer(async_session_factory, str(project_id))
        dispatch_scorer = DispatchScorer()
        info_service = InfoRequestService(async_session_factory, str(project_id))
        logger.info("[Factory] Adaptive planner enabled for project %s", project_id)

    # Phase 3: Evaluator (created early so CriticAgent can reference it)
    evaluator = None
    if settings.use_multi_eval:
        from backend.evaluation.evaluator import EvaluatorService

        evaluator = EvaluatorService(
            llm_router, project_id=str(project_id), embedding_service=embedding_service,
        )

    agents: dict[AgentRole, Any] = {
        AgentRole.DIRECTOR: DirectorAgent(
            llm_router,
            write_back_guard,
            project_id=str(project_id),
            info_request_service=info_service,
            board=board,
        ),
        AgentRole.SCIENTIST: ScientistAgent(
            llm_router,
            write_back_guard,
            project_id=str(project_id),
            info_request_service=info_service,
            board=board,
        ),
        AgentRole.LIBRARIAN: LibrarianAgent(
            llm_router,
            write_back_guard,
            project_id=str(project_id),
            embedding_model=embedding_model,
            info_request_service=info_service,
            board=board,
        ),
        AgentRole.WRITER: WriterAgent(
            llm_router,
            write_back_guard,
            project_id=str(project_id),
            info_request_service=info_service,
            board=board,
        ),
        AgentRole.CRITIC: CriticAgent(
            llm_router,
            write_back_guard,
            project_id=str(project_id),
            info_request_service=info_service,
            evaluator=evaluator,
            board=board,
        ),
        AgentRole.SYNTHESIZER: SynthesizerAgent(
            llm_router,
            write_back_guard,
            project_id=str(project_id),
            info_request_service=info_service,
            board=board,
        ),
    }

    planner = OrchestratorPlanner(
        llm_router,
        research_topic=research_topic,
        lane_perspective=lane_perspective,
        event_bus=event_bus,
        dispatch_scorer=dispatch_scorer,
    )
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
        token_tracker=token_tracker,
        lane_index=lane_index,
        embedding_service=embedding_service,
        evaluator=evaluator,
        state_analyzer=state_analyzer,
        info_request_service=info_service,
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
    """Read artifacts from all lane workspaces and build a combined context string.

    Uses async I/O (aiofiles) to avoid blocking the event loop when reading
    many artifact files across multiple lanes.  Artifacts are grouped by type
    within each lane for structured synthesis context.
    """
    max_content_chars = 6000  # per artifact (doubled from 3000)

    sections: list[str] = []
    for lane_idx in range(num_lanes):
        lane_path = project_path / "lanes" / str(lane_idx)
        artifacts_dir = lane_path / "artifacts"
        if not artifacts_dir.exists():
            continue

        # Group artifacts by type for structured output
        type_groups: dict[str, list[str]] = {}
        for art_type_dir in sorted(artifacts_dir.iterdir()):
            if not art_type_dir.is_dir():
                continue
            group_name = art_type_dir.name
            for artifact_dir in sorted(art_type_dir.iterdir()):
                if not artifact_dir.is_dir():
                    continue
                meta_path = artifact_dir / "meta.json"
                if not meta_path.exists():
                    continue
                try:
                    async with aiofiles.open(meta_path) as f:
                        meta = json.loads(await f.read())
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
                        async with aiofiles.open(l2_file) as f:
                            content = (await f.read())[:max_content_chars]
                        art_type = meta.get("artifact_type", group_name)
                        aid = meta.get("artifact_id", "")
                        type_groups.setdefault(art_type, []).append(f"#### {aid}\n{content}")
                except Exception:
                    continue

        if type_groups:
            lane_parts = [f"\n## Lane {lane_idx}\n"]
            for art_type, items in sorted(type_groups.items()):
                lane_parts.append(f"### {art_type} ({len(items)} artifacts)")
                lane_parts.extend(items)
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

    # Aggregate critic scores from all lanes into the synthesis board
    # so the convergence detector starts with correct baseline
    aggregated_scores: dict[str, float] = {}
    for lane_idx in range(num_lanes):
        lane_meta_path = project_path / "lanes" / str(lane_idx) / "meta.json"
        if lane_meta_path.exists():
            try:
                lane_meta = json.loads(lane_meta_path.read_text())
                lane_scores = lane_meta.get("phase_critic_scores", {})
                for phase_key, score in lane_scores.items():
                    existing = aggregated_scores.get(phase_key, 0.0)
                    aggregated_scores[phase_key] = max(existing, float(score))
            except Exception:
                logger.warning(
                    "[Factory] Failed to read lane %d meta for scores",
                    lane_idx,
                )
    if aggregated_scores:
        await engine._board.update_meta(
            "phase_critic_scores",
            aggregated_scores,
        )
        logger.info(
            "[Factory] Aggregated lane critic scores: %s",
            aggregated_scores,
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


def _extract_lane_overrides(
    config_json: dict | None, num_lanes: int
) -> tuple[list[dict[str, str] | None], str | None]:
    """Extract per-lane model overrides and embedding_model from config_json.

    Returns a tuple of:
    - list of length num_lanes, where each element is either
      a dict of {role: model} overrides or None (use global settings).
    - embedding_model string or None (use global settings).
    """
    if not config_json:
        return [None] * num_lanes, None
    embedding_model = config_json.get("embedding_model")
    lane_overrides_list = config_json.get("lane_overrides", [])
    if not isinstance(lane_overrides_list, list):
        return [None] * num_lanes, embedding_model
    result: list[dict[str, str] | None] = []
    for i in range(num_lanes):
        if i < len(lane_overrides_list) and lane_overrides_list[i]:
            result.append(lane_overrides_list[i])
        else:
            result.append(None)
    return result, embedding_model


async def start_engine(project_id: str) -> None:
    if project_id in _running_engines:
        logger.warning("Engine already running for project %s", project_id)
        return

    _stopped_projects.discard(project_id)

    research_topic, concurrency, config_json = await _fetch_project_info(project_id)
    lane_overrides, embedding_model = _extract_lane_overrides(config_json, max(concurrency, 1))
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
                            model_overrides=lane_overrides[0],
                            embedding_model=embedding_model,
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
                            lane_overrides,
                            embedding_model=embedding_model,
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
    lane_overrides: list[dict[str, str] | None] | None = None,
    embedding_model: str | None = None,
) -> None:
    """Run N independent lane engines concurrently, then synthesize results."""
    project_path = settings.project_path(project_id)
    broadcast = _build_ws_broadcast(project_id)

    if lane_overrides is None:
        lane_overrides = [None] * num_lanes

    # Create lane workspaces and engines
    lane_engines: list[OrchestrationEngine] = []
    for lane_idx in range(num_lanes):
        lane_path = project_path / "lanes" / str(lane_idx)
        lane_path.mkdir(parents=True, exist_ok=True)
        (lane_path / "artifacts").mkdir(exist_ok=True)

        perspective = _LANE_PERSPECTIVES[lane_idx % len(_LANE_PERSPECTIVES)]
        engine = await _create_engine(
            project_id,
            workspace_path=lane_path,
            research_topic=research_topic,
            lane_index=lane_idx,
            lane_perspective=perspective,
            model_overrides=lane_overrides[lane_idx] if lane_idx < len(lane_overrides) else None,
            embedding_model=embedding_model,
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
    lane_stagger_secs = 5  # delay between lane starts to avoid API rate limiting
    lane_max_retries = 2  # max retry attempts per lane on failure

    async def _run_lane(idx: int, eng: OrchestrationEngine) -> None:
        # Stagger lane starts to avoid concurrent API rate limiting
        if idx > 0:
            delay = idx * lane_stagger_secs
            logger.info("[Factory] Lane %d staggered by %ds", idx, delay)
            await asyncio.sleep(delay)

        for attempt in range(1, lane_max_retries + 2):
            try:
                logger.info(
                    "[Factory] Lane %d starting for project %s (attempt %d)",
                    idx,
                    project_id,
                    attempt,
                )
                await eng.run()
                logger.info("[Factory] Lane %d completed for project %s", idx, project_id)
                await broadcast("LaneCompleted", {"lane": idx})
                return
            except asyncio.CancelledError:
                logger.info("[Factory] Lane %d cancelled for project %s", idx, project_id)
                await broadcast("LaneCompleted", {"lane": idx, "error": True})
                return
            except Exception:
                logger.exception(
                    "[Factory] Lane %d failed for project %s (attempt %d/%d)",
                    idx,
                    project_id,
                    attempt,
                    lane_max_retries + 1,
                )
                if attempt <= lane_max_retries:
                    backoff = 10 * attempt
                    logger.info("[Factory] Lane %d retrying in %ds...", idx, backoff)
                    await asyncio.sleep(backoff)
                    # Re-create the engine for a clean retry
                    lane_path = project_path / "lanes" / str(idx)
                    try:
                        eng = await _create_engine(
                            project_id,
                            workspace_path=lane_path,
                            research_topic=research_topic,
                            lane_index=idx,
                            lane_perspective=_LANE_PERSPECTIVES[idx % len(_LANE_PERSPECTIVES)],
                            model_overrides=(
                                lane_overrides[idx]
                                if lane_overrides and idx < len(lane_overrides)
                                else None
                            ),
                            embedding_model=embedding_model,
                        )
                    except Exception:
                        logger.exception("[Factory] Lane %d engine re-creation failed", idx)
                        break
                else:
                    await broadcast("LaneCompleted", {"lane": idx, "error": True})

    await asyncio.gather(*[_run_lane(idx, eng) for idx, eng in enumerate(lane_engines)])

    # All lanes done -- run synthesis
    if project_id not in _stopped_projects:
        await _run_synthesis(project_id, project_path, num_lanes, research_topic)


def stop_engine(project_id: str, cancel: bool = False) -> None:
    _stopped_projects.add(project_id)
    engine = _running_engines.get(project_id)
    if engine:
        engine.stop()
    if cancel:
        task = _running_tasks.get(project_id)
        if task and not task.done():
            task.cancel()
            logger.info("Cancelled asyncio task for project %s", project_id)


def get_engine(project_id: str) -> OrchestrationEngine | None:
    return _running_engines.get(project_id)


def is_running(project_id: str) -> bool:
    return project_id in _running_engines


def get_checkpoint_manager(project_id: str) -> CheckpointManager | None:
    return _checkpoint_managers.get(project_id)
