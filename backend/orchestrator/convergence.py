"""Convergence detection for research phase transitions."""

from __future__ import annotations

import logging
from typing import Protocol

from backend.config import settings
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
    async def get_open_challenge_count(self) -> int: ...
    async def get_latest_critic_score(self) -> float: ...
    async def get_recent_revision_count(self, rounds: int) -> int: ...
    async def get_phase_iteration_count(self, phase: ResearchPhase) -> int: ...


class ConvergenceDetector:
    """Checks whether the current research phase has converged and
    should transition to the next phase.

    Convergence requires *all* of:
      - No open challenges
      - Critic score >= threshold
      - Stability (no major revisions in N rounds)

    A max-iteration guard forces transition regardless.
    """

    def __init__(
        self,
        min_critic_score: float | None = None,
        stable_rounds: int | None = None,
        max_iterations: int | None = None,
    ) -> None:
        self._min_critic_score = (
            min_critic_score
            if min_critic_score is not None
            else settings.convergence_min_critic_score
        )
        self._stable_rounds = (
            stable_rounds
            if stable_rounds is not None
            else settings.convergence_stable_rounds
        )
        self._max_iterations = (
            max_iterations
            if max_iterations is not None
            else settings.max_iterations_per_phase
        )

    async def check(
        self, board: Board, phase: ResearchPhase
    ) -> ConvergenceSignals:
        open_challenges = await board.get_open_challenge_count()
        critic_score = await board.get_latest_critic_score()
        revision_count = await board.get_recent_revision_count(
            self._stable_rounds
        )
        iteration_count = await board.get_phase_iteration_count(phase)

        converged = self.is_phase_converged(
            ConvergenceSignals(
                open_challenges=open_challenges,
                critic_score=critic_score,
                recent_revision_count=revision_count,
                iteration_count=iteration_count,
            )
        )

        return ConvergenceSignals(
            open_challenges=open_challenges,
            critic_score=critic_score,
            recent_revision_count=revision_count,
            iteration_count=iteration_count,
            is_converged=converged,
        )

    def is_phase_converged(self, signals: ConvergenceSignals) -> bool:
        if signals.iteration_count >= self._max_iterations:
            logger.info(
                "Max-iteration guard triggered at %d", signals.iteration_count
            )
            return True

        no_open = signals.open_challenges == 0
        score_ok = signals.critic_score >= self._min_critic_score
        stable = signals.recent_revision_count == 0

        return no_open and score_ok and stable

    @staticmethod
    def suggest_next_phase(current_phase: ResearchPhase) -> ResearchPhase:
        try:
            idx = _PHASE_ORDER.index(current_phase)
        except ValueError:
            return ResearchPhase.COMPLETE
        if idx + 1 < len(_PHASE_ORDER):
            return _PHASE_ORDER[idx + 1]
        return ResearchPhase.COMPLETE
