"""DispatchScorer -- deterministic per-agent scoring for adaptive planning.

Replaces fixed rotation with state-aware agent selection.
No LLM calls (except optional tie-breaker in the planner).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from backend.config import settings
from backend.orchestrator.state_analyzer import ResearchState, ResearchStateAnalyzer
from backend.types import AgentRole, ArtifactType, ResearchPhase

logger = logging.getLogger(__name__)

# Base score for all agents
_BASE_SCORE = 0.5


@dataclass
class AgentScore:
    """Scored candidate for agent dispatch."""

    role: AgentRole
    base: float = _BASE_SCORE
    need_signal: float = 0.0
    phase_bonus: float = 0.0
    request_bonus: float = 0.0
    repetition_penalty: float = 0.0
    total: float = 0.0
    rationale: str = ""

    def compute_total(self) -> None:
        self.total = (
            self.base + self.need_signal + self.phase_bonus
            + self.request_bonus - self.repetition_penalty
        )


class DispatchScorer:
    """Score agents deterministically based on research state."""

    def score_agents(
        self,
        state: ResearchState,
        phase: ResearchPhase,
        valid_agents: set[AgentRole],
        selection_history: list[tuple[int, str]] | None = None,
    ) -> list[AgentScore]:
        """Score all valid agents and return sorted (highest first).

        Args:
            state: Structured research state from analyzer.
            phase: Current research phase.
            valid_agents: Set of agents allowed in this phase.
            selection_history: Recent selections as (iteration, role_value) tuples.

        Returns:
            List of AgentScore sorted by total descending.
        """
        scores: list[AgentScore] = []
        preferred = set(ResearchStateAnalyzer.get_preferred_agents(phase))
        history = selection_history or state.selection_history or []

        for role in valid_agents:
            score = AgentScore(role=role)
            reasons: list[str] = []

            # --- Need signal (agent-specific) ---
            score.need_signal = self._compute_need_signal(role, state, reasons)

            # --- Phase bonus/penalty ---
            if role in preferred:
                score.phase_bonus = settings.adaptive_phase_bonus
                reasons.append(f"phase-preferred +{score.phase_bonus}")
            elif role not in preferred and role != AgentRole.CRITIC:
                # Critic is always allowed without penalty
                score.phase_bonus = -settings.adaptive_non_phase_penalty
                reasons.append(f"non-phase -{settings.adaptive_non_phase_penalty}")

            # --- Request bonus ---
            pending = state.pending_requests.get(role.value, 0)
            if pending > 0:
                bonus = min(
                    pending * 0.25,
                    settings.adaptive_request_bonus_cap,
                )
                score.request_bonus = bonus
                reasons.append(f"requests({pending}) +{bonus:.2f}")

            # --- Per-agent challenge bonus ---
            target_challenges = state.open_challenges_by_target.get(role.value, 0)
            if target_challenges > 0:
                ch_bonus = min(target_challenges * 0.15, 0.3)
                signal = score.need_signal + ch_bonus
                score.need_signal = signal
                reasons.append(f"targeted challenges({target_challenges}) +{ch_bonus:.2f}")

            # --- Repetition penalty ---
            if history:
                last_entry = history[-1]
                if last_entry[1] == role.value:
                    score.repetition_penalty = settings.adaptive_repetition_penalty
                    reasons.append(f"last-iter penalty -{score.repetition_penalty}")
                elif len(history) >= 2 and history[-2][1] == role.value:
                    score.repetition_penalty = settings.adaptive_repetition_penalty / 3
                    reasons.append(f"2nd-last penalty -{score.repetition_penalty:.3f}")

            score.compute_total()
            score.rationale = "; ".join(reasons) if reasons else "base"
            scores.append(score)

        scores.sort(key=lambda s: s.total, reverse=True)

        if scores:
            logger.info(
                "[DispatchScorer] Top: %s (%.2f) — %s",
                scores[0].role.value,
                scores[0].total,
                scores[0].rationale[:100],
            )

        return scores

    def _compute_need_signal(
        self,
        role: AgentRole,
        state: ResearchState,
        reasons: list[str],
    ) -> float:
        """Compute need-based signal for a specific agent role."""
        signal = 0.0

        if role == AgentRole.LIBRARIAN:
            if ArtifactType.EVIDENCE_FINDINGS in state.missing_types:
                signal += 0.3
                reasons.append("missing evidence +0.3")
            if state.unsupported_hypothesis_count > 0:
                signal += 0.2
                reasons.append(f"unsupported hypotheses({state.unsupported_hypothesis_count}) +0.2")

        elif role == AgentRole.SCIENTIST:
            if ArtifactType.HYPOTHESES in state.missing_types:
                signal += 0.3
                reasons.append("missing hypotheses +0.3")
            if state.hypothesis_count == 0:
                signal += 0.2
                reasons.append("zero hypotheses +0.2")
            if state.contradiction_count > 0:
                signal += 0.15
                reasons.append(f"contradictions({state.contradiction_count}) +0.15")

        elif role == AgentRole.DIRECTOR:
            if ArtifactType.DIRECTIONS in state.missing_types:
                signal += 0.3
                reasons.append("missing directions +0.3")
            if state.iterations_without_progress > 3:
                signal += 0.2
                reasons.append(
                    f"stagnation({state.iterations_without_progress} iters) +0.2"
                )

        elif role == AgentRole.WRITER:
            if not state.has_outline and not state.has_draft:
                signal += 0.3
                reasons.append("missing outline/draft +0.3")
            elif state.has_outline and not state.has_draft:
                signal += 0.2
                reasons.append("outline-no-draft +0.2")
            elif state.sections_needing_revision:
                signal += 0.15
                reasons.append(
                    f"sections needing revision({len(state.sections_needing_revision)}) +0.15"
                )
            if state.uncited_claim_count > 0:
                signal += 0.1
                reasons.append(f"uncited claims({state.uncited_claim_count}) +0.1")
            if state.phase == ResearchPhase.COMPOSE:
                signal += 0.15
                reasons.append("COMPOSE phase +0.15")

        elif role == AgentRole.CRITIC:
            if state.review_count == 0:
                signal += 0.3
                reasons.append("never reviewed +0.3")
            if state.open_challenge_count > 2:
                signal += 0.2
                reasons.append(f"open challenges({state.open_challenge_count}) +0.2")

        elif role == AgentRole.SYNTHESIZER:
            if state.phase == ResearchPhase.SYNTHESIZE:
                signal += 0.3
                reasons.append("SYNTHESIZE phase +0.3")

        # Cross-cutting evaluation signals
        if state.eval_composite_score is not None and state.eval_composite_score < 5.0:
            # Low evaluation score: boost critic for review
            if role == AgentRole.CRITIC:
                signal += 0.15
                reasons.append(f"low eval({state.eval_composite_score:.1f}) +0.15")
        if state.is_diminishing_returns:
            # Diminishing returns: boost director for strategy reset
            if role == AgentRole.DIRECTOR:
                signal += 0.2
                reasons.append("diminishing returns +0.2")
        if state.contradiction_count > 1:
            # Multiple contradictions: boost scientist to investigate
            if role == AgentRole.SCIENTIST:
                extra = min(state.contradiction_count * 0.1, 0.3)
                signal += extra
                reasons.append(f"contradictions({state.contradiction_count}) +{extra:.2f}")

        return signal
