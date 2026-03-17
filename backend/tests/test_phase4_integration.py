"""Integration test: adaptive planner 3-iteration loop.

Tests the full flow: StateAnalyzer → DispatchScorer → Planner → agent selection.
Does NOT require a running DB or LLM — uses mocks.
"""

from __future__ import annotations

import pytest

from backend.orchestrator.dispatch_scorer import DispatchScorer
from backend.orchestrator.planner import OrchestratorPlanner
from backend.orchestrator.state_analyzer import ResearchState, ResearchStateAnalyzer
from backend.types import AgentRole, ResearchPhase


class _MockBoard:
    """Board mock that simulates artifact accumulation across iterations."""

    def __init__(self):
        self._artifacts: dict[str, list] = {}
        self._meta: dict = {}
        self._challenges = 0
        self._critic_score = 0.0

    def add_artifact(self, artifact_type: str, artifact_id: str):
        self._artifacts.setdefault(artifact_type, []).append(artifact_id)

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
        self._meta[key] = value


class _MockRouter:
    """LLM router that never gets called in the adaptive path."""

    call_count: int = 0

    async def generate(self, *args, **kwargs):
        self.call_count += 1
        return '{"agent": "critic", "task": "review", "rationale": "fallback"}'

    def resolve_model(self, role):
        return "test-model"


class TestAdaptivePlannerIntegration:
    """Simulate 3 iterations with the adaptive planner and verify:
    1. Different agents are selected based on state
    2. Agent selection changes as artifacts accumulate
    3. No LLM calls are made (deterministic scoring)
    """

    @pytest.mark.asyncio
    async def test_three_iteration_loop(self, monkeypatch):
        # Enable adaptive planner via monkeypatch
        from backend.config import settings

        monkeypatch.setattr(settings, "use_adaptive_planner", True)

        board = _MockBoard()
        router = _MockRouter()
        scorer = DispatchScorer()
        analyzer = ResearchStateAnalyzer(None, "integration-test")

        planner = OrchestratorPlanner(
            router,
            research_topic="Effect of temperature on catalyst efficiency",
            dispatch_scorer=scorer,
        )

        selected_agents: list[AgentRole] = []
        phase = ResearchPhase.EXPLORE

        for iteration in range(1, 4):
            # Analyze state
            state = await analyzer.analyze(board, phase, iteration)

            # Plan next action
            decision = await planner.plan_next_action(
                "Board summary...",
                phase,
                iteration,
                research_state=state,
            )
            selected_agents.append(decision.agent_to_invoke)

            # Simulate agent output: first iter produces evidence, second directions
            if iteration == 1:
                board.add_artifact("evidence_findings", "ef1")
            elif iteration == 2:
                board.add_artifact("directions", "dir1")

        # Verify different agents were selected
        assert len(selected_agents) == 3
        # With empty board, first agent should be librarian or director (explore phase)
        assert selected_agents[0] in {AgentRole.LIBRARIAN, AgentRole.DIRECTOR}
        # After evidence_findings added, should not pick librarian again immediately
        # (repetition penalty + evidence no longer missing)
        assert not (
            selected_agents[0] == selected_agents[1] == selected_agents[2]
        ), "All 3 iterations picked the same agent — adaptive planner not working"

    @pytest.mark.asyncio
    async def test_no_llm_calls_with_clear_winner(self, monkeypatch):
        """When one agent has a clear lead, LLM tie-breaker should not be called."""
        from backend.config import settings

        monkeypatch.setattr(settings, "use_adaptive_planner", True)

        # Create a board where only librarian has a strong signal
        # (evidence missing but directions already exist)
        board = _MockBoard()
        board.add_artifact("directions", "dir1")
        router = _MockRouter()
        scorer = DispatchScorer()
        analyzer = ResearchStateAnalyzer(None, "test-no-llm")

        planner = OrchestratorPlanner(
            router,
            research_topic="Test topic",
            dispatch_scorer=scorer,
        )

        state = await analyzer.analyze(board, ResearchPhase.EXPLORE, 1)
        decision = await planner.plan_next_action(
            "Summary",
            ResearchPhase.EXPLORE,
            1,
            research_state=state,
        )

        # Librarian should win clearly (missing evidence + phase preferred)
        # while Director has no need signal (directions exist)
        assert decision.agent_to_invoke == AgentRole.LIBRARIAN
        assert router.call_count == 0

    @pytest.mark.asyncio
    async def test_flag_off_uses_standard_path(self, monkeypatch):
        """With flag off, planner uses existing LLM/rule path."""
        from backend.config import settings

        monkeypatch.setattr(settings, "use_adaptive_planner", False)
        monkeypatch.setattr(settings, "enable_llm_planner", False)

        router = _MockRouter()
        scorer = DispatchScorer()

        planner = OrchestratorPlanner(
            router,
            research_topic="Test topic",
            dispatch_scorer=scorer,
        )

        state = ResearchState(phase=ResearchPhase.EXPLORE, iteration=1)
        decision = await planner.plan_next_action(
            "Summary",
            ResearchPhase.EXPLORE,
            1,
            research_state=state,
        )

        # Should use rule-based selection (first in EXPLORE sequence = LIBRARIAN)
        assert decision.agent_to_invoke == AgentRole.LIBRARIAN
        assert "Rule-based" in decision.rationale or "Coverage" in decision.rationale

    @pytest.mark.asyncio
    async def test_critic_guarantee_overrides_adaptive(self, monkeypatch):
        """Critic guarantee should override adaptive selection."""
        from backend.config import settings

        monkeypatch.setattr(settings, "use_adaptive_planner", True)

        router = _MockRouter()
        scorer = DispatchScorer()

        planner = OrchestratorPlanner(
            router,
            research_topic="Test topic",
            dispatch_scorer=scorer,
        )
        # Simulate critic not called for 3 iterations
        planner._critic_last_iter["explore"] = 0

        state = ResearchState(phase=ResearchPhase.EXPLORE, iteration=3)
        decision = await planner.plan_next_action(
            "Summary",
            ResearchPhase.EXPLORE,
            3,
            research_state=state,
        )

        assert decision.agent_to_invoke == AgentRole.CRITIC
        assert "Critic guarantee" in decision.rationale
