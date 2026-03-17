"""Unit tests for ResearchStateAnalyzer."""

from __future__ import annotations

import pytest

from backend.orchestrator.state_analyzer import ResearchState, ResearchStateAnalyzer
from backend.types import AgentRole, ResearchPhase


class _MockBoard:
    """Minimal mock board for state analyzer tests."""

    def __init__(self, artifacts=None, challenges=0, critic_score=0.0, meta=None):
        self._artifacts = artifacts or {}
        self._challenges = challenges
        self._critic_score = critic_score
        self._meta = meta or {}
        self._updated_meta: dict = {}

    async def list_artifacts(self, artifact_type, include_superseded=False):
        return self._artifacts.get(artifact_type.value, [])

    async def get_open_challenge_count(self):
        return self._challenges

    async def get_phase_critic_score(self, phase):
        return self._critic_score

    async def has_contradictory_evidence(self):
        return False

    async def get_project_meta(self):
        return dict(self._meta)

    async def update_meta(self, key, value):
        self._updated_meta[key] = value


class TestResearchState:
    def test_defaults(self):
        state = ResearchState()
        assert state.phase == ResearchPhase.EXPLORE
        assert state.iteration == 0
        assert state.hypothesis_count == 0
        assert state.missing_types == []

    def test_custom_values(self):
        state = ResearchState(
            phase=ResearchPhase.COMPOSE,
            iteration=5,
            hypothesis_count=3,
            has_draft=True,
        )
        assert state.phase == ResearchPhase.COMPOSE
        assert state.iteration == 5
        assert state.has_draft is True


class TestResearchStateAnalyzer:
    @pytest.mark.asyncio
    async def test_empty_board(self):
        board = _MockBoard()
        analyzer = ResearchStateAnalyzer(None, "test-project")
        state = await analyzer.analyze(board, ResearchPhase.EXPLORE, 1)

        assert state.phase == ResearchPhase.EXPLORE
        assert state.iteration == 1
        assert state.hypothesis_count == 0
        assert state.evidence_count == 0
        assert not state.has_draft
        assert not state.has_outline

    @pytest.mark.asyncio
    async def test_with_artifacts(self):
        board = _MockBoard(
            artifacts={
                "hypotheses": ["h1", "h2"],
                "evidence_findings": ["e1"],
                "draft": ["d1"],
                "outline": ["o1"],
                "directions": ["dir1"],
            }
        )
        analyzer = ResearchStateAnalyzer(None, "test-project")
        state = await analyzer.analyze(board, ResearchPhase.COMPOSE, 3)

        assert state.hypothesis_count == 2
        assert state.evidence_count == 1
        assert state.has_draft is True
        assert state.has_outline is True
        assert state.has_directions is True

    @pytest.mark.asyncio
    async def test_missing_types_detected(self):
        board = _MockBoard()
        analyzer = ResearchStateAnalyzer(None, "test-project")
        state = await analyzer.analyze(board, ResearchPhase.EXPLORE, 1)

        # EXPLORE phase requires directions and evidence_findings
        assert len(state.missing_types) > 0

    @pytest.mark.asyncio
    async def test_unsupported_hypotheses(self):
        board = _MockBoard(
            artifacts={"hypotheses": ["h1", "h2"]}
        )
        analyzer = ResearchStateAnalyzer(None, "test-project")
        state = await analyzer.analyze(board, ResearchPhase.HYPOTHESIZE, 2)

        assert state.unsupported_hypothesis_count == 2

    @pytest.mark.asyncio
    async def test_selection_history_passed_through(self):
        board = _MockBoard()
        analyzer = ResearchStateAnalyzer(None, "test-project")
        hist = [(1, "librarian"), (2, "critic")]
        state = await analyzer.analyze(
            board, ResearchPhase.EXPLORE, 3, selection_history=hist
        )
        assert state.selection_history == hist

    @pytest.mark.asyncio
    async def test_pending_requests_passed_through(self):
        board = _MockBoard()
        analyzer = ResearchStateAnalyzer(None, "test-project")
        pending = {"scientist": 2, "librarian": 1}
        state = await analyzer.analyze(
            board, ResearchPhase.EXPLORE, 1, pending_requests=pending
        )
        assert state.pending_requests == pending

    @pytest.mark.asyncio
    async def test_open_challenges_counted(self):
        board = _MockBoard(challenges=5)
        analyzer = ResearchStateAnalyzer(None, "test-project")
        state = await analyzer.analyze(board, ResearchPhase.EXPLORE, 1)
        assert state.open_challenge_count == 5

    @pytest.mark.asyncio
    async def test_critic_score(self):
        board = _MockBoard(critic_score=7.5)
        analyzer = ResearchStateAnalyzer(None, "test-project")
        state = await analyzer.analyze(board, ResearchPhase.COMPOSE, 3)
        assert state.critic_score == 7.5

    def test_get_preferred_agents(self):
        assert AgentRole.LIBRARIAN in ResearchStateAnalyzer.get_preferred_agents(
            ResearchPhase.EXPLORE
        )
        assert AgentRole.SCIENTIST in ResearchStateAnalyzer.get_preferred_agents(
            ResearchPhase.HYPOTHESIZE
        )
        assert AgentRole.WRITER in ResearchStateAnalyzer.get_preferred_agents(
            ResearchPhase.COMPOSE
        )
        assert AgentRole.SYNTHESIZER in ResearchStateAnalyzer.get_preferred_agents(
            ResearchPhase.SYNTHESIZE
        )

    @pytest.mark.asyncio
    async def test_eval_signals_passed_through(self):
        board = _MockBoard()
        analyzer = ResearchStateAnalyzer(None, "test-project")
        state = await analyzer.analyze(
            board, ResearchPhase.COMPOSE, 3,
            eval_composite=6.5,
            info_gain=0.12,
            is_diminishing=True,
            topic_drift=True,
        )
        assert state.eval_composite_score == 6.5
        assert state.info_gain == 0.12
        assert state.is_diminishing_returns is True
        assert state.topic_drift_detected is True

    @pytest.mark.asyncio
    async def test_new_architecture_fields_have_defaults(self):
        state = ResearchState()
        assert state.sections_drafted == []
        assert state.sections_needing_revision == []
        assert state.uncited_claim_count == 0
        assert state.phase_eval_scores == {}
        assert state.open_challenges_by_target == {}
        assert state.topic_drift_detected is False
