"""Unit tests for agent pre/post hooks (Phase 4 deepening)."""

from __future__ import annotations

import pytest

from backend.agents.critic import CriticAgent
from backend.agents.director import DirectorAgent
from backend.agents.librarian import LibrarianAgent
from backend.agents.scientist import ScientistAgent
from backend.agents.synthesizer import SynthesizerAgent
from backend.agents.writer import WriterAgent
from backend.types import (
    ActionType,
    AgentResponse,
    AgentTask,
    ArtifactType,
    BlackboardAction,
    TaskPriority,
)


class _DummyRouter:
    async def generate(self, *a, **kw):
        return "{}"

    def resolve_model(self, role):
        return "test-model"


class _DummyGuard:
    async def check(self, *a, **kw):
        return []


class _MockBoard:
    """Board mock for testing pre_execute with board queries."""

    def __init__(self, artifacts=None):
        self._artifacts = artifacts or {}

    async def list_artifacts(self, artifact_type, include_superseded=False):
        return self._artifacts.get(artifact_type.value, [])

    async def get_open_challenges(self):
        return []

    async def get_open_challenge_count(self):
        return 0


def _make_task(desc: str = "Test task") -> AgentTask:
    return AgentTask(
        task_id="test-1",
        description=desc,
        priority=TaskPriority.NORMAL,
    )


class TestDirectorHooks:
    @pytest.mark.asyncio
    async def test_pre_execute_extracts_rqs(self):
        agent = DirectorAgent(_DummyRouter(), _DummyGuard())
        context = "Some context.\nRQ1: What is the effect of X?\nRQ2: How does Y work?"
        result = await agent.pre_execute(context, _make_task())
        assert "Research Map" in result
        assert "RQ1" in result
        assert "RQ2" in result

    @pytest.mark.asyncio
    async def test_pre_execute_no_rqs(self):
        agent = DirectorAgent(_DummyRouter(), _DummyGuard())
        context = "Some context with no research questions."
        result = await agent.pre_execute(context, _make_task())
        assert result == context  # unchanged

    @pytest.mark.asyncio
    async def test_post_execute_passthrough(self):
        agent = DirectorAgent(_DummyRouter(), _DummyGuard())
        resp = AgentResponse(reasoning_summary="test")
        result = await agent.post_execute(resp, "", _make_task())
        assert result is resp


class TestScientistHooks:
    @pytest.mark.asyncio
    async def test_pre_execute_extracts_hypotheses(self):
        agent = ScientistAgent(_DummyRouter(), _DummyGuard())
        context = (
            "Analysis.\nH1: Higher temperature increases yield."
            "\nH2: Catalyst A is more effective."
        )
        result = await agent.pre_execute(context, _make_task())
        assert "Hypothesis Registry" in result

    @pytest.mark.asyncio
    async def test_post_execute_no_crash_on_empty(self):
        agent = ScientistAgent(_DummyRouter(), _DummyGuard())
        resp = AgentResponse()
        result = await agent.post_execute(resp, "", _make_task())
        assert result is resp


class TestCriticHooks:
    @pytest.mark.asyncio
    async def test_pre_execute_injects_checklist(self):
        agent = CriticAgent(_DummyRouter(), _DummyGuard())
        task = _make_task("Review for the explore phase")
        context = "Current state."
        result = await agent.pre_execute(context, task)
        assert "Review Framework" in result
        assert "Coverage" in result

    @pytest.mark.asyncio
    async def test_pre_execute_no_phase_match(self):
        agent = CriticAgent(_DummyRouter(), _DummyGuard())
        task = _make_task("Some generic task")
        context = "Current state."
        result = await agent.pre_execute(context, task)
        # No phase matched, should return context unchanged
        assert result == context


class TestWriterHooks:
    @pytest.mark.asyncio
    async def test_pre_execute_extracts_claims(self):
        agent = WriterAgent(_DummyRouter(), _DummyGuard())
        context = (
            "Studies show that X increases Y. "
            "Research indicates that Z is effective. "
            "Some other text."
        )
        result = await agent.pre_execute(context, _make_task())
        assert "Claim-Evidence Map" in result

    @pytest.mark.asyncio
    async def test_post_execute_warns_on_uncited(self):
        """Post-hook should detect draft claims without citations (logged, not error)."""
        agent = WriterAgent(_DummyRouter(), _DummyGuard())
        action = BlackboardAction(
            agent_role="writer",
            action_type="write_artifact",
            target="draft",
            content={"text": "Studies show that X is effective. " * 10},
        )
        resp = AgentResponse(actions=[action])
        result = await agent.post_execute(resp, "", _make_task())
        assert result is resp  # no crash


class TestLibrarianHooks:
    @pytest.mark.asyncio
    async def test_pre_execute_extracts_gaps(self):
        agent = LibrarianAgent(_DummyRouter(), _DummyGuard())
        context = "The analysis reveals an evidence gap: no data on long-term effects."
        result = await agent.pre_execute(context, _make_task())
        assert "Evidence Gaps" in result

    @pytest.mark.asyncio
    async def test_pre_execute_no_gaps(self):
        agent = LibrarianAgent(_DummyRouter(), _DummyGuard())
        context = "All evidence is complete."
        result = await agent.pre_execute(context, _make_task())
        assert result == context


class TestSynthesizerHooks:
    @pytest.mark.asyncio
    async def test_pre_execute_detects_lanes(self):
        agent = SynthesizerAgent(_DummyRouter(), _DummyGuard())
        context = "## Lane 0\n### hypotheses\nH1\n## Lane 1\n### evidence\nE1"
        result = await agent.pre_execute(context, _make_task())
        assert "Cross-Lane Comparison" in result
        assert "Lane 0" in result

    @pytest.mark.asyncio
    async def test_pre_execute_single_lane(self):
        agent = SynthesizerAgent(_DummyRouter(), _DummyGuard())
        context = "## Lane 0\n### hypotheses\nH1"
        result = await agent.pre_execute(context, _make_task())
        # Single lane, no comparison matrix
        assert result == context

    @pytest.mark.asyncio
    async def test_post_execute_no_crash(self):
        agent = SynthesizerAgent(_DummyRouter(), _DummyGuard())
        resp = AgentResponse()
        result = await agent.post_execute(resp, "", _make_task())
        assert result is resp


class TestBoardQueryHooks:
    """Test that pre_execute uses board queries when board is available."""

    @pytest.mark.asyncio
    async def test_director_queries_board(self):
        board = _MockBoard(artifacts={
            "directions": ["RQ1: What is X?"],
            "hypotheses": ["H1", "H2"],
            "evidence_findings": ["E1"],
        })
        agent = DirectorAgent(_DummyRouter(), _DummyGuard(), board=board)
        result = await agent.pre_execute("Context.", _make_task())
        assert "Research Map (from board)" in result
        assert "Directions: 1" in result
        assert "Hypotheses: 2" in result

    @pytest.mark.asyncio
    async def test_scientist_queries_board(self):
        board = _MockBoard(artifacts={
            "hypotheses": ["H1: Temperature increases yield"],
            "evidence_findings": ["E1: supports H1"],
        })
        agent = ScientistAgent(_DummyRouter(), _DummyGuard(), board=board)
        result = await agent.pre_execute("Context.", _make_task())
        assert "Hypothesis Registry (from board)" in result
        assert "Total hypotheses: 1" in result

    @pytest.mark.asyncio
    async def test_writer_queries_board(self):
        board = _MockBoard(artifacts={
            "evidence_findings": ["E1", "E2"],
            "hypotheses": ["H1"],
            "draft": [],
            "outline": ["O1"],
        })
        agent = WriterAgent(_DummyRouter(), _DummyGuard(), board=board)
        result = await agent.pre_execute("Context.", _make_task())
        assert "Claim-Evidence Map (from board)" in result
        assert "Evidence artifacts: 2" in result

    @pytest.mark.asyncio
    async def test_librarian_queries_board_gaps(self):
        board = _MockBoard(artifacts={
            "evidence_gaps": ["Gap: long-term effects"],
            "hypotheses": ["H1"],
            "evidence_findings": [],
        })
        agent = LibrarianAgent(_DummyRouter(), _DummyGuard(), board=board)
        result = await agent.pre_execute("Context.", _make_task())
        assert "Evidence Gaps (from board)" in result
        assert "NO supporting evidence" in result

    @pytest.mark.asyncio
    async def test_synthesizer_queries_board(self):
        board = _MockBoard(artifacts={
            "hypotheses": ["H1", "H2"],
            "evidence_findings": ["E1"],
            "review": ["R1"],
            "draft": ["D1"],
        })
        agent = SynthesizerAgent(_DummyRouter(), _DummyGuard(), board=board)
        context = "## Lane 0\n### hypotheses\nH1\n## Lane 1\n### evidence\nE1"
        result = await agent.pre_execute(context, _make_task())
        assert "Cross-Lane Comparison Matrix (from board)" in result

    @pytest.mark.asyncio
    async def test_scientist_raises_challenge_on_missing_falsification(self):
        agent = ScientistAgent(_DummyRouter(), _DummyGuard())
        action = BlackboardAction(
            agent_role="scientist",
            action_type=ActionType.WRITE_ARTIFACT,
            target=ArtifactType.HYPOTHESES.value,
            content={"text": "Hypothesis 1: Temperature increases yield. " * 5},
        )
        resp = AgentResponse(actions=[action])
        result = await agent.post_execute(resp, "", _make_task())
        # Should have appended a RAISE_CHALLENGE action
        challenge_actions = [
            a for a in result.actions if a.action_type == ActionType.RAISE_CHALLENGE
        ]
        assert len(challenge_actions) == 1
        assert "falsification" in challenge_actions[0].content["argument"]
