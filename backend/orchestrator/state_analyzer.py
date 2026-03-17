"""ResearchStateAnalyzer -- extract structured state from board for adaptive planning.

Pure computation, no LLM calls. Target: <100ms.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from backend.types import AgentRole, ArtifactType, ResearchPhase

logger = logging.getLogger(__name__)


@dataclass
class ResearchState:
    """Structured snapshot of the current research state."""

    # Artifact counts by type
    artifact_counts: dict[str, int] = field(default_factory=dict)
    # Artifact types that are required but missing for the current phase
    missing_types: list[ArtifactType] = field(default_factory=list)

    # Hypothesis stats
    hypothesis_count: int = 0
    unsupported_hypothesis_count: int = 0
    contradiction_count: int = 0

    # Evidence
    evidence_count: int = 0
    evidence_gap_count: int = 0

    # Writing readiness
    has_outline: bool = False
    has_draft: bool = False
    has_directions: bool = False

    # Quality signals
    critic_score: float = 0.0
    review_count: int = 0
    open_challenge_count: int = 0

    # Pending inter-agent requests (responder_role -> count)
    pending_requests: dict[str, int] = field(default_factory=dict)

    # Progress tracking
    phase: ResearchPhase = ResearchPhase.EXPLORE
    iteration: int = 0
    iterations_without_progress: int = 0

    # Selection history: list of (iteration, agent_role_value) tuples
    selection_history: list[tuple[int, str]] = field(default_factory=list)

    # Writing analysis (architecture §6.1 required fields)
    sections_drafted: list[str] = field(default_factory=list)
    sections_needing_revision: list[str] = field(default_factory=list)
    uncited_claim_count: int = 0

    # Per-phase evaluation history
    phase_eval_scores: dict[str, float] = field(default_factory=dict)

    # Challenges grouped by target agent
    open_challenges_by_target: dict[str, int] = field(default_factory=dict)

    # Topic drift signal (from engine's on-topic check)
    topic_drift_detected: bool = False

    # Evaluation signals (from Phase 3 EvaluatorService)
    eval_composite_score: float | None = None
    info_gain: float | None = None
    is_diminishing_returns: bool = False
    contradiction_details: list[dict] = field(default_factory=list)


class ResearchStateAnalyzer:
    """Extracts structured ResearchState from the board and DB.

    All operations are fast (filesystem/cache reads + simple DB queries).
    No LLM calls.
    """

    def __init__(
        self,
        session_factory,
        project_id: str,
    ) -> None:
        self._session_factory = session_factory
        self._project_id = project_id

    async def analyze(
        self,
        board,
        phase: ResearchPhase,
        iteration: int,
        *,
        selection_history: list[tuple[int, str]] | None = None,
        pending_requests: dict[str, int] | None = None,
        eval_composite: float | None = None,
        info_gain: float | None = None,
        is_diminishing: bool = False,
        contradictions: list[dict] | None = None,
        topic_drift: bool = False,
    ) -> ResearchState:
        """Build a ResearchState snapshot from the current board state.

        Args:
            board: The blackboard (Board protocol).
            phase: Current research phase.
            iteration: Current iteration number.
            selection_history: Recent agent selection history.
            pending_requests: Pre-computed pending request counts by responder role.
        """
        state = ResearchState(phase=phase, iteration=iteration)

        if selection_history:
            state.selection_history = list(selection_history)
        if pending_requests:
            state.pending_requests = dict(pending_requests)

        # Count artifacts by type
        for at in ArtifactType:
            try:
                arts = await board.list_artifacts(at)
                count = len(arts)
            except Exception:
                count = 0
            state.artifact_counts[at.value] = count

        state.hypothesis_count = state.artifact_counts.get(ArtifactType.HYPOTHESES.value, 0)
        state.evidence_count = state.artifact_counts.get(
            ArtifactType.EVIDENCE_FINDINGS.value, 0
        )
        state.evidence_gap_count = state.artifact_counts.get(ArtifactType.EVIDENCE_GAPS.value, 0)
        state.review_count = state.artifact_counts.get(ArtifactType.REVIEW.value, 0)
        state.has_outline = state.artifact_counts.get(ArtifactType.OUTLINE.value, 0) > 0
        state.has_draft = state.artifact_counts.get(ArtifactType.DRAFT.value, 0) > 0
        state.has_directions = state.artifact_counts.get(ArtifactType.DIRECTIONS.value, 0) > 0

        # Missing artifact types for current phase
        from backend.orchestrator.convergence import get_phase_required_artifacts

        required = get_phase_required_artifacts(phase)
        state.missing_types = [
            at for at in required if state.artifact_counts.get(at.value, 0) == 0
        ]

        # Unsupported hypotheses: hypotheses exist but no evidence
        if state.hypothesis_count > 0 and state.evidence_count == 0:
            state.unsupported_hypothesis_count = state.hypothesis_count

        # Contradiction / quality signals from board
        try:
            state.open_challenge_count = await board.get_open_challenge_count()
        except Exception:
            pass

        try:
            if await board.has_contradictory_evidence():
                state.contradiction_count = max(state.contradiction_count, 1)
        except Exception:
            pass

        try:
            state.critic_score = await board.get_phase_critic_score(phase)
        except Exception:
            pass

        # Stagnation detection: iterations without new artifacts
        try:
            meta = await board.get_project_meta()
            prev_total = meta.get("__analyzer_prev_artifact_total", 0)
            current_total = sum(state.artifact_counts.values())
            if current_total <= prev_total and iteration > 1:
                state.iterations_without_progress = meta.get(
                    "__analyzer_iters_no_progress", 0
                ) + 1
            else:
                state.iterations_without_progress = 0
            # Persist for next iteration (board.update_meta is fire-and-forget here)
            await board.update_meta("__analyzer_prev_artifact_total", current_total)
            await board.update_meta(
                "__analyzer_iters_no_progress", state.iterations_without_progress
            )
        except Exception:
            pass

        # Writing analysis: extract section info from draft artifacts
        try:
            drafts = await board.list_artifacts(ArtifactType.DRAFT)
            if drafts:
                import re
                # Parse section headers from most recent draft
                last_draft = drafts[-1] if isinstance(drafts[-1], str) else str(drafts[-1])
                state.sections_drafted = re.findall(
                    r"^#+\s+(.+)$", last_draft, re.MULTILINE
                )[:20]
        except Exception:
            pass

        # Challenges by target agent
        try:
            challenges = await board.get_open_challenges()
            for ch in challenges:
                target = getattr(ch, "target_agent", None)
                if target:
                    key = target.value if hasattr(target, "value") else str(target)
                    state.open_challenges_by_target[key] = (
                        state.open_challenges_by_target.get(key, 0) + 1
                    )
        except Exception:
            pass

        # Topic drift (passed in from engine)
        state.topic_drift_detected = topic_drift

        # Evaluation signals (passed in from engine's evaluator)
        if eval_composite is not None:
            state.eval_composite_score = eval_composite
        if info_gain is not None:
            state.info_gain = info_gain
        state.is_diminishing_returns = is_diminishing
        if contradictions:
            state.contradiction_details = contradictions
            state.contradiction_count = max(state.contradiction_count, len(contradictions))

        logger.debug(
            "[StateAnalyzer] phase=%s iter=%d artifacts=%s missing=%s challenges=%d",
            phase.value,
            iteration,
            {k: v for k, v in state.artifact_counts.items() if v > 0},
            [at.value for at in state.missing_types],
            state.open_challenge_count,
        )
        return state

    @staticmethod
    def get_preferred_agents(phase: ResearchPhase) -> list[AgentRole]:
        """Return the set of agents preferred for a given phase."""
        phase_preferred: dict[ResearchPhase, list[AgentRole]] = {
            ResearchPhase.EXPLORE: [AgentRole.LIBRARIAN, AgentRole.DIRECTOR],
            ResearchPhase.HYPOTHESIZE: [AgentRole.SCIENTIST, AgentRole.DIRECTOR],
            ResearchPhase.EVIDENCE: [AgentRole.LIBRARIAN, AgentRole.SCIENTIST],
            ResearchPhase.COMPOSE: [AgentRole.WRITER],
            ResearchPhase.SYNTHESIZE: [AgentRole.SYNTHESIZER],
            ResearchPhase.COMPLETE: [AgentRole.CRITIC, AgentRole.WRITER],
        }
        return phase_preferred.get(phase, [])
