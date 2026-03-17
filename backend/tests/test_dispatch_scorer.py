"""Unit tests for DispatchScorer."""

from __future__ import annotations

from backend.orchestrator.dispatch_scorer import AgentScore, DispatchScorer
from backend.orchestrator.state_analyzer import ResearchState
from backend.types import AgentRole, ArtifactType, ResearchPhase


class TestAgentScore:
    def test_compute_total(self):
        score = AgentScore(
            role=AgentRole.LIBRARIAN,
            base=0.5,
            need_signal=0.3,
            phase_bonus=0.2,
            request_bonus=0.25,
            repetition_penalty=0.15,
        )
        score.compute_total()
        assert abs(score.total - 1.1) < 0.01


class TestDispatchScorer:
    def setup_method(self):
        self.scorer = DispatchScorer()

    def test_empty_valid_agents(self):
        state = ResearchState()
        scores = self.scorer.score_agents(state, ResearchPhase.EXPLORE, set())
        assert scores == []

    def test_librarian_high_when_evidence_missing(self):
        state = ResearchState(
            phase=ResearchPhase.EXPLORE,
            missing_types=[ArtifactType.EVIDENCE_FINDINGS],
        )
        valid = {AgentRole.LIBRARIAN, AgentRole.DIRECTOR, AgentRole.CRITIC}
        scores = self.scorer.score_agents(state, ResearchPhase.EXPLORE, valid)

        # Librarian should be top (missing evidence + phase preferred)
        assert scores[0].role == AgentRole.LIBRARIAN
        assert scores[0].need_signal >= 0.3

    def test_scientist_high_when_no_hypotheses(self):
        state = ResearchState(
            phase=ResearchPhase.HYPOTHESIZE,
            hypothesis_count=0,
            missing_types=[ArtifactType.HYPOTHESES],
        )
        valid = {AgentRole.SCIENTIST, AgentRole.DIRECTOR, AgentRole.CRITIC}
        scores = self.scorer.score_agents(state, ResearchPhase.HYPOTHESIZE, valid)

        assert scores[0].role == AgentRole.SCIENTIST
        assert scores[0].need_signal >= 0.5  # 0.3 + 0.2

    def test_director_high_when_stagnant(self):
        state = ResearchState(
            phase=ResearchPhase.EXPLORE,
            iterations_without_progress=5,
            missing_types=[ArtifactType.DIRECTIONS],
        )
        valid = {AgentRole.LIBRARIAN, AgentRole.DIRECTOR, AgentRole.CRITIC}
        scores = self.scorer.score_agents(state, ResearchPhase.EXPLORE, valid)

        director_score = next(s for s in scores if s.role == AgentRole.DIRECTOR)
        assert director_score.need_signal >= 0.5  # 0.3 + 0.2

    def test_writer_high_in_compose_no_draft(self):
        state = ResearchState(
            phase=ResearchPhase.COMPOSE,
            has_outline=True,
            has_draft=False,
        )
        valid = {AgentRole.WRITER, AgentRole.CRITIC}
        scores = self.scorer.score_agents(state, ResearchPhase.COMPOSE, valid)

        assert scores[0].role == AgentRole.WRITER
        # 0.2 (outline-no-draft) + 0.15 (COMPOSE) + 0.2 (phase preferred)
        assert scores[0].total > scores[1].total

    def test_critic_high_when_never_reviewed(self):
        state = ResearchState(
            phase=ResearchPhase.EXPLORE,
            review_count=0,
        )
        valid = {AgentRole.LIBRARIAN, AgentRole.CRITIC}
        scores = self.scorer.score_agents(state, ResearchPhase.EXPLORE, valid)

        critic_score = next(s for s in scores if s.role == AgentRole.CRITIC)
        assert critic_score.need_signal >= 0.3

    def test_repetition_penalty_last_iter(self):
        state = ResearchState(phase=ResearchPhase.EXPLORE)
        history = [(1, "librarian")]
        valid = {AgentRole.LIBRARIAN, AgentRole.DIRECTOR, AgentRole.CRITIC}
        scores = self.scorer.score_agents(
            state, ResearchPhase.EXPLORE, valid, selection_history=history
        )

        librarian_score = next(s for s in scores if s.role == AgentRole.LIBRARIAN)
        assert librarian_score.repetition_penalty > 0

    def test_request_bonus(self):
        state = ResearchState(
            phase=ResearchPhase.EXPLORE,
            pending_requests={"scientist": 2},
        )
        valid = {AgentRole.SCIENTIST, AgentRole.LIBRARIAN, AgentRole.CRITIC}
        scores = self.scorer.score_agents(state, ResearchPhase.EXPLORE, valid)

        scientist_score = next(s for s in scores if s.role == AgentRole.SCIENTIST)
        assert scientist_score.request_bonus > 0

    def test_request_bonus_cap(self):
        state = ResearchState(
            phase=ResearchPhase.EXPLORE,
            pending_requests={"scientist": 10},
        )
        valid = {AgentRole.SCIENTIST}
        scores = self.scorer.score_agents(state, ResearchPhase.EXPLORE, valid)
        # Cap is 0.5
        assert scores[0].request_bonus <= 0.5

    def test_scores_sorted_descending(self):
        state = ResearchState(
            phase=ResearchPhase.EXPLORE,
            missing_types=[ArtifactType.EVIDENCE_FINDINGS],
        )
        valid = {AgentRole.LIBRARIAN, AgentRole.DIRECTOR, AgentRole.CRITIC}
        scores = self.scorer.score_agents(state, ResearchPhase.EXPLORE, valid)

        for i in range(len(scores) - 1):
            assert scores[i].total >= scores[i + 1].total

    def test_phase_penalty_for_non_preferred(self):
        state = ResearchState(phase=ResearchPhase.COMPOSE)
        valid = {AgentRole.WRITER, AgentRole.CRITIC, AgentRole.SCIENTIST}
        scores = self.scorer.score_agents(state, ResearchPhase.COMPOSE, valid)

        # Scientist should have negative phase bonus (not preferred in COMPOSE)
        scientist_score = next(s for s in scores if s.role == AgentRole.SCIENTIST)
        assert scientist_score.phase_bonus < 0

    def test_synthesizer_in_synthesize_phase(self):
        state = ResearchState(phase=ResearchPhase.SYNTHESIZE)
        valid = {AgentRole.SYNTHESIZER, AgentRole.CRITIC}
        scores = self.scorer.score_agents(state, ResearchPhase.SYNTHESIZE, valid)

        assert scores[0].role == AgentRole.SYNTHESIZER
        assert scores[0].need_signal >= 0.3
