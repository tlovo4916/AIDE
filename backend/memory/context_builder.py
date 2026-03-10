"""Context builder -- assembles agent context within token budget."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from backend.config import settings
from backend.memory.token_budget import TokenBudget
from backend.types import AgentRole, AgentTask, ArtifactType, ContextLevel

if TYPE_CHECKING:
    from backend.blackboard.active_tracker import ActiveTracker
    from backend.blackboard.board import Blackboard

logger = logging.getLogger(__name__)

OWN_ARTIFACTS: dict[AgentRole, set[ArtifactType]] = {
    AgentRole.DIRECTOR: {ArtifactType.DIRECTIONS, ArtifactType.EXPERIMENT_GUIDE},
    AgentRole.SCIENTIST: {
        ArtifactType.HYPOTHESES,
        ArtifactType.EVIDENCE_FINDINGS,
        ArtifactType.EVIDENCE_GAPS,
    },
    AgentRole.LIBRARIAN: {
        ArtifactType.EVIDENCE_FINDINGS,
        ArtifactType.EVIDENCE_GAPS,
    },
    AgentRole.WRITER: {ArtifactType.OUTLINE, ArtifactType.DRAFT},
    AgentRole.CRITIC: {ArtifactType.REVIEW},
}

DEPENDENCY_ARTIFACTS: dict[AgentRole, set[ArtifactType]] = {
    AgentRole.DIRECTOR: {
        ArtifactType.HYPOTHESES,
        ArtifactType.EVIDENCE_FINDINGS,
        ArtifactType.REVIEW,
    },
    AgentRole.SCIENTIST: {
        ArtifactType.DIRECTIONS,
        ArtifactType.EXPERIMENT_GUIDE,
    },
    AgentRole.LIBRARIAN: {
        ArtifactType.HYPOTHESES,
        ArtifactType.DIRECTIONS,
    },
    AgentRole.WRITER: {
        ArtifactType.DIRECTIONS,
        ArtifactType.HYPOTHESES,
        ArtifactType.EVIDENCE_FINDINGS,
        ArtifactType.OUTLINE,
    },
    AgentRole.CRITIC: {
        ArtifactType.DRAFT,
        ArtifactType.HYPOTHESES,
        ArtifactType.EVIDENCE_FINDINGS,
    },
}


class ContextBuilder:
    def __init__(
        self,
        active_tracker: ActiveTracker | None = None,
    ) -> None:
        self._tracker = active_tracker

    async def build(
        self,
        agent_role: AgentRole,
        task: AgentTask,
        board: Blackboard,
        knowledge_base: Any = None,
    ) -> str:
        budget = TokenBudget(settings.context_budget_tokens)

        core = await self._build_core(board)
        budget.allocate("Core Context", core, max_ratio=settings.core_ratio, fixed=True)

        task_ctx = await self._build_task_context(agent_role, board)
        budget.allocate("Task Context", task_ctx, max_ratio=settings.task_ratio)

        cross_ctx = await self._build_cross_context(agent_role, board)
        budget.allocate(
            "Cross-Agent Context",
            cross_ctx,
            max_ratio=settings.cross_ratio,
        )

        lit_ctx = await self._build_literature_context(task, knowledge_base)
        budget.allocate(
            "Literature Context",
            lit_ctx,
            max_ratio=settings.literature_ratio,
        )

        history_ctx = await self._build_history_context(agent_role, board)
        budget.allocate(
            "History Context",
            history_ctx,
            max_ratio=settings.history_ratio,
        )

        return budget.assemble()

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    async def _build_core(self, board: Blackboard) -> str:
        meta = await board.get_project_meta()
        project_l0 = (
            f"Project: {meta.get('name', 'Unknown')} | Phase: {meta.get('phase', 'explore')}"
        )
        decisions = await board.get_decisions()
        if decisions:
            recent = decisions[-5:]
            digest = "\n".join(f"- {d.chosen}: {d.rationale[:100]}" for d in recent)
        else:
            digest = "No decisions yet."
        return f"{project_l0}\n\nRecent decisions:\n{digest}"

    async def _build_task_context(
        self,
        agent_role: AgentRole,
        board: Blackboard,
    ) -> str:
        parts: list[str] = []
        own_types = OWN_ARTIFACTS.get(agent_role, set())
        dep_types = DEPENDENCY_ARTIFACTS.get(agent_role, set())

        for at in own_types:
            metas = await board.list_artifacts(at)
            for m in metas:
                ver = await board.get_latest_version(at, m.artifact_id)
                if ver == 0:
                    continue
                content = await self._load_and_track(
                    board,
                    at,
                    m.artifact_id,
                    ver,
                    ContextLevel.L2,
                )
                if content:
                    parts.append(f"[{at.value}/{m.artifact_id} v{ver}]\n{content}")

        for at in dep_types:
            metas = await board.list_artifacts(at)
            for m in metas:
                ver = await board.get_latest_version(at, m.artifact_id)
                if ver == 0:
                    continue
                content = await self._load_and_track(
                    board,
                    at,
                    m.artifact_id,
                    ver,
                    ContextLevel.L1,
                )
                if content:
                    summary = (
                        json.dumps(content, ensure_ascii=False)
                        if isinstance(content, dict)
                        else str(content)
                    )
                    parts.append(f"[{at.value}/{m.artifact_id} v{ver} (L1)]\n{summary}")

        return "\n\n".join(parts) if parts else "No task artifacts available."

    async def _build_cross_context(
        self,
        agent_role: AgentRole,
        board: Blackboard,
    ) -> str:
        parts: list[str] = []
        own_types = OWN_ARTIFACTS.get(agent_role, set())
        dep_types = DEPENDENCY_ARTIFACTS.get(agent_role, set())
        already_included = own_types | dep_types

        for at in ArtifactType:
            if at in already_included:
                continue
            metas = await board.list_artifacts(at)
            for m in metas:
                ver = await board.get_latest_version(at, m.artifact_id)
                if ver == 0:
                    continue
                content = await self._load_and_track(
                    board,
                    at,
                    m.artifact_id,
                    ver,
                    ContextLevel.L1,
                )
                if content:
                    summary = (
                        json.dumps(content, ensure_ascii=False)
                        if isinstance(content, dict)
                        else str(content)
                    )
                    parts.append(f"[{at.value}/{m.artifact_id} (L1)]\n{summary}")

        challenges = await board.get_open_challenges()
        for ch in challenges:
            parts.append(
                f"[CHALLENGE {ch.challenge_id}] "
                f"{ch.challenger.value} challenges {ch.target_artifact}: "
                f"{ch.argument}"
            )

        return "\n\n".join(parts) if parts else "No cross-agent context available."

    @staticmethod
    async def _build_literature_context(
        task: AgentTask,
        knowledge_base: Any,
    ) -> str:
        if knowledge_base is None:
            return "No literature search available."
        try:
            results = await knowledge_base.search(task.description, top_k=10)
            parts = [f"[{r.source}] (score: {r.score:.2f})\n{r.content}" for r in results]
            return "\n\n".join(parts) if parts else "No relevant literature found."
        except Exception as exc:
            logger.warning("Literature search failed: %s", exc)
            return "Literature search failed."

    async def _build_history_context(
        self,
        agent_role: AgentRole,
        board: Blackboard,
    ) -> str:
        parts: list[str] = []
        own_types = OWN_ARTIFACTS.get(agent_role, set())

        for at in own_types:
            metas = await board.list_artifacts(at, include_superseded=True)
            for m in metas:
                latest = await board.get_latest_version(at, m.artifact_id)
                chain: list[str] = []
                for v in range(1, latest + 1):
                    l0 = await board.read_artifact(
                        at,
                        m.artifact_id,
                        v,
                        ContextLevel.L0,
                    )
                    if l0 and isinstance(l0, str):
                        chain.append(f"v{v}: {l0}")
                if chain:
                    parts.append(f"[{at.value}/{m.artifact_id}]\n" + "\n".join(chain))

        return "\n\n".join(parts) if parts else "No evolution history available."

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _load_and_track(
        self,
        board: Blackboard,
        artifact_type: ArtifactType,
        artifact_id: str,
        version: int,
        level: ContextLevel,
    ) -> str | dict | None:
        content = await board.read_artifact(
            artifact_type,
            artifact_id,
            version,
            level,
        )
        if content and self._tracker:
            await self._tracker.increment(board, artifact_type, artifact_id)
        return content
