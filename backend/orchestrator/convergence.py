"""Convergence detection for research phase transitions."""

from __future__ import annotations

import logging

from backend.config import settings
from backend.protocols import Board
from backend.types import ArtifactType, ConvergenceSignals, ResearchPhase

logger = logging.getLogger(__name__)

_PHASE_ORDER = [
    ResearchPhase.EXPLORE,
    ResearchPhase.HYPOTHESIZE,
    ResearchPhase.EVIDENCE,
    ResearchPhase.COMPOSE,
    ResearchPhase.SYNTHESIZE,
    ResearchPhase.COMPLETE,
]

# Per-phase default score thresholds (can be overridden via config)
_PHASE_SCORE_THRESHOLDS: dict[ResearchPhase, float] = {
    ResearchPhase.EXPLORE: 6.0,
    ResearchPhase.HYPOTHESIZE: 6.5,
    ResearchPhase.EVIDENCE: 7.0,
    ResearchPhase.COMPOSE: 7.5,
    ResearchPhase.SYNTHESIZE: 7.0,
}

# Per-phase required artifact types (at least 1 non-superseded each)
_PHASE_REQUIRED_ARTIFACTS: dict[ResearchPhase, set[ArtifactType]] = {
    ResearchPhase.EXPLORE: {ArtifactType.EVIDENCE_FINDINGS, ArtifactType.DIRECTIONS},
    ResearchPhase.HYPOTHESIZE: {ArtifactType.HYPOTHESES, ArtifactType.DIRECTIONS},
    ResearchPhase.EVIDENCE: {ArtifactType.EVIDENCE_FINDINGS},
    ResearchPhase.COMPOSE: {ArtifactType.DRAFT},
    ResearchPhase.SYNTHESIZE: {ArtifactType.DRAFT},
}


def get_phase_required_artifacts(phase: ResearchPhase) -> set[ArtifactType]:
    """Return the set of artifact types required for a phase to converge."""
    return _PHASE_REQUIRED_ARTIFACTS.get(phase, set())


class ConvergenceDetector:
    """Checks whether the current research phase has converged and
    should transition to the next phase.

    Convergence requires *all* of:
      - No open challenges
      - Critic score >= per-phase threshold
      - Required artifact types have at least 1 non-superseded artifact
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
            stable_rounds if stable_rounds is not None else settings.convergence_stable_rounds
        )
        self._max_iterations = (
            max_iterations if max_iterations is not None else settings.max_iterations_per_phase
        )

    def _get_phase_threshold(self, phase: ResearchPhase) -> float:
        """Return the critic score threshold for a phase, with config override support."""
        override = settings.convergence_phase_thresholds.get(phase.value)
        if override is not None:
            return float(override)
        return _PHASE_SCORE_THRESHOLDS.get(phase, self._min_critic_score)

    async def check(
        self,
        board: Board,
        phase: ResearchPhase,
        eval_composite: float | None = None,
        information_gain: float | None = None,
        is_diminishing: bool = False,
    ) -> ConvergenceSignals:
        open_challenges = await board.get_open_challenge_count()
        critic_score = await board.get_phase_critic_score(phase)
        revision_count = await board.get_recent_revision_count(self._stable_rounds)
        iteration_count = await board.get_phase_iteration_count(phase)

        # Check artifact coverage
        coverage_ok = await self._check_artifact_coverage(board, phase)

        converged = self._is_phase_converged(
            ConvergenceSignals(
                open_challenges=open_challenges,
                critic_score=critic_score,
                recent_revision_count=revision_count,
                iteration_count=iteration_count,
                eval_composite=eval_composite,
                information_gain=information_gain,
                is_diminishing=is_diminishing,
            ),
            phase,
            coverage_ok,
        )

        return ConvergenceSignals(
            open_challenges=open_challenges,
            critic_score=critic_score,
            recent_revision_count=revision_count,
            iteration_count=iteration_count,
            is_converged=converged,
            eval_composite=eval_composite,
            information_gain=information_gain,
            is_diminishing=is_diminishing,
        )

    async def _check_artifact_coverage(self, board: Board, phase: ResearchPhase) -> bool:
        """Check that all required artifact types for this phase have at least 1 artifact."""
        required = _PHASE_REQUIRED_ARTIFACTS.get(phase, set())
        if not required:
            return True
        for art_type in required:
            artifacts = await board.list_artifacts(art_type)
            if not artifacts:
                logger.debug(
                    "[Convergence] Missing required artifact type %s for phase %s",
                    art_type.value,
                    phase.value,
                )
                return False
        return True

    def _is_phase_converged(
        self,
        signals: ConvergenceSignals,
        phase: ResearchPhase,
        coverage_ok: bool = True,
    ) -> bool:
        if signals.iteration_count >= self._max_iterations:
            logger.info("Max-iteration guard triggered at %d", signals.iteration_count)
            return True

        threshold = self._get_phase_threshold(phase)
        no_open = signals.open_challenges == 0
        score_ok = signals.critic_score >= threshold

        # Evaluation-enhanced convergence (feature-flagged)
        eval_ok = True
        if settings.use_multi_eval and signals.eval_composite is not None:
            # Normalized threshold: phase threshold is on 0-10 scale, eval on 0-1
            eval_threshold = threshold * 0.1
            eval_score_ok = signals.eval_composite >= eval_threshold
            # Allow convergence with diminishing returns only after half max iterations
            diminishing_ok = (
                not signals.is_diminishing or signals.iteration_count >= self._max_iterations * 0.5
            )
            eval_ok = eval_score_ok and diminishing_ok
            logger.info(
                "[Convergence] eval_composite=%.3f (need >= %.3f) is_diminishing=%s eval_ok=%s",
                signals.eval_composite,
                eval_threshold,
                signals.is_diminishing,
                eval_ok,
            )

        logger.info(
            "[Convergence] phase=%s iter=%d open_challenges=%d critic_score=%.1f "
            "(need >= %.1f) coverage=%s -> no_open=%s score_ok=%s eval_ok=%s",
            phase.value,
            signals.iteration_count,
            signals.open_challenges,
            signals.critic_score,
            threshold,
            coverage_ok,
            no_open,
            score_ok,
            eval_ok,
        )

        return no_open and score_ok and coverage_ok and eval_ok

    # Keep old method name for backward compatibility
    def is_phase_converged(self, signals: ConvergenceSignals) -> bool:
        return self._is_phase_converged(signals, ResearchPhase.EXPLORE)

    @staticmethod
    def suggest_next_phase(current_phase: ResearchPhase) -> ResearchPhase:
        try:
            idx = _PHASE_ORDER.index(current_phase)
        except ValueError:
            return ResearchPhase.COMPLETE
        if idx + 1 < len(_PHASE_ORDER):
            return _PHASE_ORDER[idx + 1]
        return ResearchPhase.COMPLETE
