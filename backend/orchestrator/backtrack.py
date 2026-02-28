"""Backtrack controller for phase regression with version preservation."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Protocol

from backend.types import ConvergenceSignals, ResearchPhase

logger = logging.getLogger(__name__)

_PHASE_ORDER = [
    ResearchPhase.EXPLORE,
    ResearchPhase.HYPOTHESIZE,
    ResearchPhase.EVIDENCE,
    ResearchPhase.COMPOSE,
    ResearchPhase.COMPLETE,
]


class Board(Protocol):
    async def get_artifacts_since_phase(
        self, phase: ResearchPhase
    ) -> list[str]: ...
    async def mark_superseded(self, artifact_id: str) -> None: ...
    async def update_meta(self, key: str, value: object) -> None: ...
    async def has_contradictory_evidence(self) -> bool: ...
    async def has_logic_gaps(self) -> bool: ...
    async def has_direction_issues(self) -> bool: ...


class BacktrackController:
    """Decides when and where to regress to an earlier research phase.

    Backtrack triggers:
      - Contradictory evidence found
      - Logic gaps in the writing phase
      - Fundamental direction issues

    Artifacts from superseded phases are marked but *never* deleted --
    full version history is preserved.
    """

    async def should_backtrack(
        self,
        board: Board,
        current_phase: ResearchPhase,
        signals: ConvergenceSignals,
    ) -> Optional[ResearchPhase]:
        if current_phase == ResearchPhase.EXPLORE:
            return None

        if await board.has_contradictory_evidence():
            logger.info("Contradictory evidence detected")
            return self._target_for_contradiction(current_phase)

        if await board.has_logic_gaps():
            logger.info("Logic gaps detected in writing artifacts")
            return self._target_for_logic_gaps(current_phase)

        if await board.has_direction_issues():
            logger.info("Fundamental direction issues detected")
            return ResearchPhase.EXPLORE

        if signals.iteration_count >= 15 and signals.critic_score < 4.0:
            logger.info("Persistent low quality, suggesting phase regression")
            return self._previous_phase(current_phase)

        return None

    async def execute_backtrack(
        self, board: Board, target_phase: ResearchPhase
    ) -> None:
        target_idx = _PHASE_ORDER.index(target_phase)
        phases_to_supersede = _PHASE_ORDER[target_idx + 1 :]

        for phase in phases_to_supersede:
            artifact_ids = await board.get_artifacts_since_phase(phase)
            for aid in artifact_ids:
                await board.mark_superseded(aid)
            if artifact_ids:
                logger.info(
                    "Marked %d artifacts from phase %s as superseded",
                    len(artifact_ids),
                    phase.value,
                )

        source_phase = (
            _PHASE_ORDER[target_idx + 1]
            if target_idx + 1 < len(_PHASE_ORDER)
            else target_phase
        )
        await board.update_meta(
            "last_backtrack",
            {
                "from_phase": source_phase.value,
                "to_phase": target_phase.value,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _target_for_contradiction(
        current_phase: ResearchPhase,
    ) -> ResearchPhase:
        idx = _PHASE_ORDER.index(current_phase)
        if idx >= _PHASE_ORDER.index(ResearchPhase.EVIDENCE):
            return ResearchPhase.HYPOTHESIZE
        return ResearchPhase.EXPLORE

    @staticmethod
    def _target_for_logic_gaps(
        current_phase: ResearchPhase,
    ) -> ResearchPhase:
        idx = _PHASE_ORDER.index(current_phase)
        if idx >= _PHASE_ORDER.index(ResearchPhase.COMPOSE):
            return ResearchPhase.EVIDENCE
        return ResearchPhase.HYPOTHESIZE

    @staticmethod
    def _previous_phase(current_phase: ResearchPhase) -> ResearchPhase:
        idx = _PHASE_ORDER.index(current_phase)
        return _PHASE_ORDER[max(0, idx - 1)]
