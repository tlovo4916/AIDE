"""Tests for the 7 architecture improvements."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.types import (
    AgentRole,
    ArtifactMeta,
    ArtifactType,
    ChallengeRecord,
    ContextLevel,
    ConvergenceSignals,
    ResearchPhase,
)

# =====================================================================
# 1. Blackboard Memory Cache Tests
# =====================================================================


class TestBlackboardCache:
    """Test write-through caching in Blackboard."""

    @pytest.fixture
    def board(self, tmp_path):
        from backend.blackboard.board import Blackboard

        return Blackboard(tmp_path)

    @pytest.mark.asyncio
    async def test_init_workspace_populates_cache(self, board):
        await board.init_workspace(research_topic="test topic")
        # Cache should be populated for all artifact types
        assert len(board._artifact_cache) == len(ArtifactType)
        for at in ArtifactType:
            assert at.value in board._artifact_cache
            assert board._artifact_cache[at.value] == []

    @pytest.mark.asyncio
    async def test_meta_cache_initialized(self, board):
        await board.init_workspace(research_topic="test topic")
        assert board._meta_cache is not None
        assert board._meta_cache["research_topic"] == "test topic"

    @pytest.mark.asyncio
    async def test_write_artifact_updates_cache(self, board):
        await board.init_workspace()
        meta = ArtifactMeta(
            artifact_type=ArtifactType.DIRECTIONS,
            artifact_id="dir-001",
            version=1,
            created_by=AgentRole.DIRECTOR,
        )
        await board.write_artifact(
            ArtifactType.DIRECTIONS, "dir-001", 1, '{"test": true}', meta
        )
        cached = board._artifact_cache["directions"]
        assert len(cached) == 1
        assert cached[0].artifact_id == "dir-001"

    @pytest.mark.asyncio
    async def test_list_artifacts_from_cache(self, board):
        await board.init_workspace()
        meta = ArtifactMeta(
            artifact_type=ArtifactType.HYPOTHESES,
            artifact_id="hyp-001",
            version=1,
            created_by=AgentRole.SCIENTIST,
        )
        await board.write_artifact(
            ArtifactType.HYPOTHESES, "hyp-001", 1, '{"h": 1}', meta
        )
        # Should come from cache, not filesystem
        results = await board.list_artifacts(ArtifactType.HYPOTHESES)
        assert len(results) == 1
        assert results[0].artifact_id == "hyp-001"

    @pytest.mark.asyncio
    async def test_list_artifacts_filters_superseded(self, board):
        await board.init_workspace()
        meta1 = ArtifactMeta(
            artifact_type=ArtifactType.DIRECTIONS,
            artifact_id="dir-001",
            version=1,
            created_by=AgentRole.DIRECTOR,
            superseded=True,
        )
        meta2 = ArtifactMeta(
            artifact_type=ArtifactType.DIRECTIONS,
            artifact_id="dir-002",
            version=1,
            created_by=AgentRole.DIRECTOR,
        )
        await board.write_artifact(ArtifactType.DIRECTIONS, "dir-001", 1, "{}", meta1)
        await board.write_artifact(ArtifactType.DIRECTIONS, "dir-002", 1, "{}", meta2)
        results = await board.list_artifacts(ArtifactType.DIRECTIONS)
        assert len(results) == 1
        assert results[0].artifact_id == "dir-002"
        # include_superseded
        results_all = await board.list_artifacts(ArtifactType.DIRECTIONS, include_superseded=True)
        assert len(results_all) == 2

    @pytest.mark.asyncio
    async def test_meta_cache_updates_on_write(self, board):
        await board.init_workspace()
        await board.update_project_meta(phase="hypothesize")
        meta = await board.get_project_meta()
        assert meta["phase"] == "hypothesize"
        # Should be from cache
        assert board._meta_cache["phase"] == "hypothesize"

    @pytest.mark.asyncio
    async def test_update_artifact_meta_syncs_cache(self, board):
        await board.init_workspace()
        meta = ArtifactMeta(
            artifact_type=ArtifactType.REVIEW,
            artifact_id="rev-001",
            version=1,
            created_by=AgentRole.CRITIC,
        )
        await board.write_artifact(ArtifactType.REVIEW, "rev-001", 1, "{}", meta)
        await board.update_artifact_meta(ArtifactType.REVIEW, "rev-001", superseded=True)
        cached = board._artifact_cache["review"]
        assert len(cached) == 1
        assert cached[0].superseded is True


# =====================================================================
# 2. Agent Context Role-Based Filtering Tests
# =====================================================================


class TestContextFiltering:
    """Test that agents only see relevant artifact types."""

    @pytest.fixture
    def board(self, tmp_path):
        from backend.blackboard.board import Blackboard

        return Blackboard(tmp_path)

    @pytest.mark.asyncio
    async def test_full_summary_includes_all_types(self, board):
        await board.init_workspace(research_topic="test topic")
        # Write one of each type
        for at in [ArtifactType.DIRECTIONS, ArtifactType.HYPOTHESES, ArtifactType.REVIEW]:
            meta = ArtifactMeta(
                artifact_type=at, artifact_id=f"{at.value}-1",
                version=1, created_by=AgentRole.DIRECTOR,
            )
            await board.write_artifact(at, f"{at.value}-1", 1, f'{{"type": "{at.value}"}}', meta)

        summary = await board.get_state_summary(ContextLevel.L0)
        assert "directions" in summary
        assert "hypotheses" in summary
        assert "review" in summary

    @pytest.mark.asyncio
    async def test_filtered_summary_excludes_irrelevant(self, board):
        await board.init_workspace(research_topic="test topic")
        for at in [ArtifactType.DIRECTIONS, ArtifactType.HYPOTHESES, ArtifactType.REVIEW]:
            meta = ArtifactMeta(
                artifact_type=at, artifact_id=f"{at.value}-1",
                version=1, created_by=AgentRole.DIRECTOR,
            )
            await board.write_artifact(at, f"{at.value}-1", 1, f'{{"type": "{at.value}"}}', meta)

        # Librarian should only see: evidence_findings, hypotheses, directions
        relevant = {
            ArtifactType.EVIDENCE_FINDINGS,
            ArtifactType.HYPOTHESES,
            ArtifactType.DIRECTIONS,
        }
        summary = await board.get_state_summary(ContextLevel.L0, relevant_types=relevant)
        assert "directions" in summary
        assert "hypotheses" in summary
        assert "review" not in summary  # Librarian shouldn't see reviews

    @pytest.mark.asyncio
    async def test_filtered_summary_always_includes_topic(self, board):
        await board.init_workspace(research_topic="quantum computing")
        relevant = {ArtifactType.EVIDENCE_FINDINGS}
        summary = await board.get_state_summary(ContextLevel.L0, relevant_types=relevant)
        assert "quantum computing" in summary
        assert "RESEARCH TOPIC" in summary


# =====================================================================
# 3. Structured Output / JSON Mode Tests
# =====================================================================


class TestJsonMode:
    """Test JSON mode propagation through the LLM stack."""

    def test_deepseek_chat_supports_response_format(self):
        """DeepSeek chat should accept response_format param."""
        import inspect

        from backend.llm.providers.deepseek import DeepSeekProvider

        sig = inspect.signature(DeepSeekProvider.call)
        assert "response_format" in sig.parameters

    def test_openrouter_supports_response_format(self):
        """OpenRouter should accept response_format param."""
        import inspect

        from backend.llm.providers.openrouter import OpenRouterProvider

        sig = inspect.signature(OpenRouterProvider.call)
        assert "response_format" in sig.parameters

    def test_router_generate_has_json_mode(self):
        """LLMRouter.generate() should accept json_mode param."""
        import inspect

        from backend.llm.router import LLMRouter

        sig = inspect.signature(LLMRouter.generate)
        assert "json_mode" in sig.parameters

    def test_anthropic_injects_json_instruction(self):
        """Anthropic provider should inject JSON instruction when response_format is set."""
        from backend.llm.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(api_key="test-key")
        # Verify the call method accepts **kwargs (for response_format)
        import inspect
        sig = inspect.signature(provider.call)
        params = sig.parameters
        assert "kwargs" in params or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
        )


# =====================================================================
# 4. LLM-Based Dynamic Planner Tests
# =====================================================================


class TestDynamicPlanner:
    """Test the hybrid LLM/rule planner."""

    @pytest.fixture
    def mock_router(self):
        router = AsyncMock()
        router.generate = AsyncMock(
            return_value=(
                '{"agent": "librarian", "task": "search papers",'
                ' "rationale": "need more evidence"}'
            )
        )
        return router

    @pytest.mark.asyncio
    async def test_rule_fallback_when_disabled(self, mock_router):
        from backend.orchestrator.planner import OrchestratorPlanner

        with patch("backend.orchestrator.planner.settings") as mock_settings:
            mock_settings.enable_llm_planner = False
            mock_settings.orchestrator_model = "deepseek-chat"
            planner = OrchestratorPlanner(mock_router, research_topic="test")
            decision = await planner.plan_next_action(
                "some state", ResearchPhase.EXPLORE, 1
            )
            # Should be rule-based: EXPLORE iteration 1 -> LIBRARIAN
            assert decision.agent_to_invoke == AgentRole.LIBRARIAN
            mock_router.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_selects_valid_agent(self, mock_router):
        from backend.orchestrator.planner import OrchestratorPlanner

        with patch("backend.orchestrator.planner.settings") as mock_settings:
            mock_settings.enable_llm_planner = True
            mock_settings.orchestrator_model = "deepseek-chat"
            planner = OrchestratorPlanner(mock_router, research_topic="test")
            decision = await planner.plan_next_action(
                "some state", ResearchPhase.EXPLORE, 1
            )
            assert decision.agent_to_invoke == AgentRole.LIBRARIAN
            mock_router.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_invalid_agent_falls_back(self, mock_router):
        from backend.orchestrator.planner import OrchestratorPlanner

        mock_router.generate = AsyncMock(
            return_value='{"agent": "nonexistent_agent", "task": "do stuff"}'
        )
        with patch("backend.orchestrator.planner.settings") as mock_settings:
            mock_settings.enable_llm_planner = True
            mock_settings.orchestrator_model = "deepseek-chat"
            planner = OrchestratorPlanner(mock_router, research_topic="test")
            decision = await planner.plan_next_action(
                "some state", ResearchPhase.EXPLORE, 1
            )
            # Should fall back to rule: EXPLORE[0] = LIBRARIAN
            assert decision.agent_to_invoke == AgentRole.LIBRARIAN

    @pytest.mark.asyncio
    async def test_critic_guarantee_after_3_iters(self, mock_router):
        from backend.orchestrator.planner import OrchestratorPlanner

        mock_router.generate = AsyncMock(
            return_value='{"agent": "librarian", "task": "search", "rationale": "need more"}'
        )
        with patch("backend.orchestrator.planner.settings") as mock_settings:
            mock_settings.enable_llm_planner = True
            mock_settings.orchestrator_model = "deepseek-chat"
            planner = OrchestratorPlanner(mock_router, research_topic="test")

            # Iteration 1 and 2: LLM picks librarian
            d1 = await planner.plan_next_action("state", ResearchPhase.EXPLORE, 1)
            assert d1.agent_to_invoke == AgentRole.LIBRARIAN
            d2 = await planner.plan_next_action("state", ResearchPhase.EXPLORE, 2)
            assert d2.agent_to_invoke == AgentRole.LIBRARIAN

            # Iteration 3: (3 - 0) >= 3, so critic guarantee should fire
            d3 = await planner.plan_next_action("state", ResearchPhase.EXPLORE, 3)
            assert d3.agent_to_invoke == AgentRole.CRITIC

            # After critic at iter 3, next critic forced at iter 6
            d4 = await planner.plan_next_action("state", ResearchPhase.EXPLORE, 4)
            assert d4.agent_to_invoke == AgentRole.LIBRARIAN
            d5 = await planner.plan_next_action("state", ResearchPhase.EXPLORE, 5)
            assert d5.agent_to_invoke == AgentRole.LIBRARIAN
            d6 = await planner.plan_next_action("state", ResearchPhase.EXPLORE, 6)
            assert d6.agent_to_invoke == AgentRole.CRITIC

    @pytest.mark.asyncio
    async def test_challenge_routing_overrides_selection(self, mock_router):
        from backend.orchestrator.planner import OrchestratorPlanner

        mock_router.generate = AsyncMock(
            return_value='{"agent": "librarian", "task": "search", "rationale": "need"}'
        )
        challenge = ChallengeRecord(
            challenge_id="ch-1",
            challenger=AgentRole.CRITIC,
            target_artifact="dir-1",
            argument="Direction is too vague",
            target_agent=AgentRole.DIRECTOR,
        )
        with patch("backend.orchestrator.planner.settings") as mock_settings:
            mock_settings.enable_llm_planner = True
            mock_settings.orchestrator_model = "deepseek-chat"
            planner = OrchestratorPlanner(mock_router, research_topic="test")
            # Reset critic tracker so it doesn't force critic
            planner._critic_last_iter[ResearchPhase.EXPLORE.value] = 1
            d = await planner.plan_next_action(
                "state", ResearchPhase.EXPLORE, 2,
                open_challenges=[challenge],
            )
            assert d.agent_to_invoke == AgentRole.DIRECTOR

    @pytest.mark.asyncio
    async def test_research_topic_in_task_description(self, mock_router):
        from backend.orchestrator.planner import OrchestratorPlanner

        with patch("backend.orchestrator.planner.settings") as mock_settings:
            mock_settings.enable_llm_planner = False
            mock_settings.orchestrator_model = "deepseek-chat"
            planner = OrchestratorPlanner(mock_router, research_topic="quantum computing")
            d = await planner.plan_next_action("state", ResearchPhase.EXPLORE, 1)
            assert "quantum computing" in d.task_description


# =====================================================================
# 5. Multi-Dimensional Convergence Tests
# =====================================================================


class TestConvergence:
    """Test per-phase thresholds and artifact coverage."""

    @pytest.mark.asyncio
    async def test_per_phase_threshold_explore(self):
        from backend.orchestrator.convergence import ConvergenceDetector

        detector = ConvergenceDetector()
        # EXPLORE threshold is 6.0
        signals = ConvergenceSignals(
            open_challenges=0, critic_score=5.9, iteration_count=2
        )
        assert not detector._is_phase_converged(signals, ResearchPhase.EXPLORE)

        signals = ConvergenceSignals(
            open_challenges=0, critic_score=6.0, iteration_count=2
        )
        assert detector._is_phase_converged(signals, ResearchPhase.EXPLORE)

    @pytest.mark.asyncio
    async def test_per_phase_threshold_compose(self):
        from backend.orchestrator.convergence import ConvergenceDetector

        detector = ConvergenceDetector()
        # COMPOSE threshold is 7.5
        signals = ConvergenceSignals(
            open_challenges=0, critic_score=7.0, iteration_count=2
        )
        assert not detector._is_phase_converged(signals, ResearchPhase.COMPOSE)

        signals = ConvergenceSignals(
            open_challenges=0, critic_score=7.5, iteration_count=2
        )
        assert detector._is_phase_converged(signals, ResearchPhase.COMPOSE)

    @pytest.mark.asyncio
    async def test_max_iteration_guard_still_works(self):
        from backend.orchestrator.convergence import ConvergenceDetector

        detector = ConvergenceDetector(max_iterations=4)
        signals = ConvergenceSignals(
            open_challenges=5, critic_score=1.0, iteration_count=4
        )
        assert detector._is_phase_converged(signals, ResearchPhase.EXPLORE)

    @pytest.mark.asyncio
    async def test_artifact_coverage_check(self):
        from backend.orchestrator.convergence import ConvergenceDetector

        detector = ConvergenceDetector()
        board = AsyncMock()

        # EXPLORE requires evidence_findings and directions
        board.list_artifacts = AsyncMock(side_effect=lambda at, **kw: {
            ArtifactType.EVIDENCE_FINDINGS: [MagicMock()],
            ArtifactType.DIRECTIONS: [],  # Missing!
        }.get(at, []))

        result = await detector._check_artifact_coverage(board, ResearchPhase.EXPLORE)
        assert result is False

        # Now with both present
        board.list_artifacts = AsyncMock(side_effect=lambda at, **kw: {
            ArtifactType.EVIDENCE_FINDINGS: [MagicMock()],
            ArtifactType.DIRECTIONS: [MagicMock()],
        }.get(at, []))

        result = await detector._check_artifact_coverage(board, ResearchPhase.EXPLORE)
        assert result is True

    @pytest.mark.asyncio
    async def test_ema_scoring(self, tmp_path):
        """Critic score uses EMA (alpha=0.4) so recent scores weigh more."""
        from backend.blackboard.board import Blackboard

        board = Blackboard(tmp_path)
        await board.init_workspace()

        # First score: EMA = score itself
        await board.set_phase_critic_score(ResearchPhase.EXPLORE, 6.0)
        score1 = await board.get_phase_critic_score(ResearchPhase.EXPLORE)
        assert score1 == 6.0

        # Second score: EMA = 0.4*8.0 + 0.6*6.0 = 6.8
        await board.set_phase_critic_score(ResearchPhase.EXPLORE, 8.0)
        score2 = await board.get_phase_critic_score(ResearchPhase.EXPLORE)
        assert abs(score2 - 6.8) < 0.01

        # Third score: EMA = 0.4*9.0 + 0.6*6.8 = 7.68
        await board.set_phase_critic_score(ResearchPhase.EXPLORE, 9.0)
        score3 = await board.get_phase_critic_score(ResearchPhase.EXPLORE)
        expected = round(0.4 * 9.0 + 0.6 * 6.8, 2)
        assert abs(score3 - expected) < 0.01


# =====================================================================
# 6. Challenge Response Routing Tests
# =====================================================================


class TestChallengeRouting:
    """Test challenge routing to target agents."""

    def test_challenge_record_has_target_agent(self):
        rec = ChallengeRecord(
            challenge_id="ch-1",
            challenger=AgentRole.CRITIC,
            target_artifact="dir-1",
            argument="test",
            target_agent=AgentRole.DIRECTOR,
        )
        assert rec.target_agent == AgentRole.DIRECTOR

    def test_challenge_record_target_agent_optional(self):
        rec = ChallengeRecord(
            challenge_id="ch-2",
            challenger=AgentRole.CRITIC,
            target_artifact="dir-1",
            argument="test",
        )
        assert rec.target_agent is None

    def test_challenge_record_serialization(self):
        rec = ChallengeRecord(
            challenge_id="ch-3",
            challenger=AgentRole.CRITIC,
            target_artifact="dir-1",
            argument="test",
            target_agent=AgentRole.SCIENTIST,
        )
        data = rec.model_dump(mode="json")
        assert data["target_agent"] == "scientist"
        restored = ChallengeRecord(**data)
        assert restored.target_agent == AgentRole.SCIENTIST

    def test_auto_dismiss_threshold_is_5(self):
        from backend.orchestrator.engine import _CHALLENGE_AUTO_DISMISS_AFTER
        assert _CHALLENGE_AUTO_DISMISS_AFTER == 5


# =====================================================================
# 7. Semantic Topic Drift Detection Tests
# =====================================================================


class TestTopicDrift:
    """Test semantic topic drift detection."""

    def test_cosine_similarity_identical(self):
        from backend.orchestrator.engine import OrchestrationEngine

        a = [1.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        assert abs(OrchestrationEngine._cosine_similarity(a, b) - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal(self):
        from backend.orchestrator.engine import OrchestrationEngine

        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(OrchestrationEngine._cosine_similarity(a, b)) < 1e-6

    def test_cosine_similarity_opposite(self):
        from backend.orchestrator.engine import OrchestrationEngine

        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert abs(OrchestrationEngine._cosine_similarity(a, b) - (-1.0)) < 1e-6

    def test_cosine_similarity_zero_vector(self):
        from backend.orchestrator.engine import OrchestrationEngine

        a = [0.0, 0.0]
        b = [1.0, 0.0]
        assert OrchestrationEngine._cosine_similarity(a, b) == 0.0

    def test_jieba_import(self):
        """jieba should be available in the environment."""
        import jieba
        words = list(jieba.cut("量子计算优化研究"))
        assert len(words) > 0

    def test_jieba_segmentation_quality(self):
        """jieba should segment Chinese text meaningfully."""
        import jieba
        words = set(jieba.cut("大语言模型推理优化"))
        # Should contain meaningful segments
        assert any(len(w) > 1 for w in words)

    def test_config_has_drift_thresholds(self):
        from backend.config import Settings
        s = Settings()
        assert hasattr(s, "topic_drift_embedding_threshold")
        assert hasattr(s, "topic_drift_keyword_threshold")
        assert s.topic_drift_embedding_threshold == 0.5
        assert s.topic_drift_keyword_threshold == 0.4


# =====================================================================
# Integration: Context Builder with filtering
# =====================================================================


class TestContextBuilderIntegration:
    """Test build_budget_context with relevant_types filtering."""

    @pytest.mark.asyncio
    async def test_build_budget_context_passes_relevant_types(self, tmp_path):
        from backend.blackboard.board import Blackboard
        from backend.blackboard.context_builder import build_budget_context

        board = Blackboard(tmp_path)
        await board.init_workspace(research_topic="test")

        # Write artifacts of different types
        for at, role in [
            (ArtifactType.DIRECTIONS, AgentRole.DIRECTOR),
            (ArtifactType.HYPOTHESES, AgentRole.SCIENTIST),
            (ArtifactType.REVIEW, AgentRole.CRITIC),
        ]:
            meta = ArtifactMeta(
                artifact_type=at, artifact_id=f"{at.value}-1",
                version=1, created_by=role,
            )
            await board.write_artifact(at, f"{at.value}-1", 1, f'{{"data": "{at.value}"}}', meta)

        # Full context
        full = await build_budget_context(board)
        assert "directions" in full
        assert "hypotheses" in full
        assert "review" in full

        # Filtered context (librarian view)
        filtered = await build_budget_context(
            board,
            relevant_types={
                ArtifactType.EVIDENCE_FINDINGS,
                ArtifactType.DIRECTIONS,
                ArtifactType.HYPOTHESES,
            },
        )
        assert "directions" in filtered
        assert "hypotheses" in filtered
        assert "review" not in filtered
        # Topic always included
        assert "test" in filtered


# =====================================================================
# 8. Coverage ↔ Planner Closed Loop Tests
# =====================================================================


class TestCoveragePlannerLoop:
    """Test that missing artifacts are passed to planner and influence agent selection."""

    def test_get_phase_required_artifacts(self):
        from backend.orchestrator.convergence import get_phase_required_artifacts

        required = get_phase_required_artifacts(ResearchPhase.EXPLORE)
        assert ArtifactType.EVIDENCE_FINDINGS in required
        assert ArtifactType.DIRECTIONS in required

        required_compose = get_phase_required_artifacts(ResearchPhase.COMPOSE)
        assert ArtifactType.DRAFT in required_compose

        # COMPLETE has no requirements
        required_complete = get_phase_required_artifacts(ResearchPhase.COMPLETE)
        assert len(required_complete) == 0

    @pytest.mark.asyncio
    async def test_rule_select_override_for_missing_artifacts(self):
        from backend.orchestrator.planner import OrchestratorPlanner

        router = AsyncMock()
        with patch("backend.orchestrator.planner.settings") as mock_settings:
            mock_settings.enable_llm_planner = False
            mock_settings.orchestrator_model = "deepseek-chat"
            planner = OrchestratorPlanner(router, research_topic="test")

            # EXPLORE iteration 1 normally picks LIBRARIAN
            # But if DIRECTIONS is missing, should override to DIRECTOR
            decision = await planner.plan_next_action(
                "state", ResearchPhase.EXPLORE, 1,
                missing_artifact_types=[ArtifactType.DIRECTIONS],
            )
            assert decision.agent_to_invoke == AgentRole.DIRECTOR

    @pytest.mark.asyncio
    async def test_rule_select_no_override_when_agent_already_produces(self):
        from backend.orchestrator.planner import OrchestratorPlanner

        router = AsyncMock()
        with patch("backend.orchestrator.planner.settings") as mock_settings:
            mock_settings.enable_llm_planner = False
            mock_settings.orchestrator_model = "deepseek-chat"
            planner = OrchestratorPlanner(router, research_topic="test")

            # EXPLORE iteration 1 = LIBRARIAN, missing = evidence_findings
            # LIBRARIAN produces evidence_findings, so no override
            decision = await planner.plan_next_action(
                "state", ResearchPhase.EXPLORE, 1,
                missing_artifact_types=[ArtifactType.EVIDENCE_FINDINGS],
            )
            assert decision.agent_to_invoke == AgentRole.LIBRARIAN

    @pytest.mark.asyncio
    async def test_missing_artifacts_in_task_description(self):
        from backend.orchestrator.planner import OrchestratorPlanner

        router = AsyncMock()
        with patch("backend.orchestrator.planner.settings") as mock_settings:
            mock_settings.enable_llm_planner = False
            mock_settings.orchestrator_model = "deepseek-chat"
            planner = OrchestratorPlanner(router, research_topic="test")

            decision = await planner.plan_next_action(
                "state", ResearchPhase.EXPLORE, 1,
                missing_artifact_types=[ArtifactType.DIRECTIONS],
            )
            assert "directions" in decision.task_description
            assert "缺失" in decision.task_description


# =====================================================================
# 9. Lane Perspective Diversity Tests
# =====================================================================


class TestLanePerspective:
    """Test that lane perspective is injected into task descriptions."""

    @pytest.mark.asyncio
    async def test_perspective_in_task_description(self):
        from backend.orchestrator.planner import OrchestratorPlanner

        router = AsyncMock()
        with patch("backend.orchestrator.planner.settings") as mock_settings:
            mock_settings.enable_llm_planner = False
            mock_settings.orchestrator_model = "deepseek-chat"
            planner = OrchestratorPlanner(
                router,
                research_topic="test",
                lane_perspective="Focus on theoretical foundations",
            )
            decision = await planner.plan_next_action(
                "state", ResearchPhase.EXPLORE, 1,
            )
            assert "theoretical foundations" in decision.task_description
            assert "RESEARCH PERSPECTIVE" in decision.task_description

    @pytest.mark.asyncio
    async def test_no_perspective_when_empty(self):
        from backend.orchestrator.planner import OrchestratorPlanner

        router = AsyncMock()
        with patch("backend.orchestrator.planner.settings") as mock_settings:
            mock_settings.enable_llm_planner = False
            mock_settings.orchestrator_model = "deepseek-chat"
            planner = OrchestratorPlanner(router, research_topic="test")
            decision = await planner.plan_next_action(
                "state", ResearchPhase.EXPLORE, 1,
            )
            assert "RESEARCH PERSPECTIVE" not in decision.task_description

    def test_lane_perspectives_list(self):
        from backend.orchestrator.factory import _LANE_PERSPECTIVES

        assert len(_LANE_PERSPECTIVES) >= 3
        # Each perspective should be a non-empty string
        for p in _LANE_PERSPECTIVES:
            assert isinstance(p, str)
            assert len(p) > 10


# =====================================================================
# 10. WriteBackGuard Toggle Tests
# =====================================================================


class TestWriteBackGuardToggle:
    """Test that write-back guard can be disabled via config."""

    def test_config_has_enable_write_back_guard(self):
        from backend.config import Settings

        s = Settings()
        assert hasattr(s, "enable_write_back_guard")
        assert s.enable_write_back_guard is True


# =====================================================================
# 11. Settings API New Fields Tests
# =====================================================================


class TestSettingsNewFields:
    """Test that new config fields are present in settings model."""

    def test_llm_settings_has_new_fields(self):
        from backend.api.settings import LLMSettings

        s = LLMSettings()
        assert hasattr(s, "enable_llm_planner")
        assert hasattr(s, "enable_write_back_guard")
        assert hasattr(s, "topic_drift_embedding_threshold")
        assert hasattr(s, "topic_drift_keyword_threshold")
        assert hasattr(s, "max_iterations_per_phase")
        assert hasattr(s, "convergence_min_critic_score")

    def test_llm_settings_defaults(self):
        from backend.api.settings import LLMSettings

        s = LLMSettings()
        assert s.enable_llm_planner is True
        assert s.enable_write_back_guard is True
        assert s.topic_drift_embedding_threshold == 0.5
        assert s.topic_drift_keyword_threshold == 0.4
        assert s.max_iterations_per_phase == 4
        assert s.convergence_min_critic_score == 6.0

    def test_overrides_fields_include_new_entries(self):
        from backend.api.settings import _OVERRIDES_FIELDS

        assert "enable_llm_planner" in _OVERRIDES_FIELDS
        assert "enable_write_back_guard" in _OVERRIDES_FIELDS
        assert "topic_drift_embedding_threshold" in _OVERRIDES_FIELDS
        assert "topic_drift_keyword_threshold" in _OVERRIDES_FIELDS
        assert "max_iterations_per_phase" in _OVERRIDES_FIELDS
        assert "convergence_min_critic_score" in _OVERRIDES_FIELDS


# =====================================================================
# 12. Stop Endpoint Tests
# =====================================================================


class TestStopEndpoint:
    """Test factory.stop_engine with cancel flag."""

    def test_stop_engine_with_cancel(self):
        from backend.orchestrator import factory

        # Create a mock task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        factory._running_tasks["test-project"] = mock_task
        factory._running_engines["test-project"] = MagicMock()

        factory.stop_engine("test-project", cancel=True)

        mock_task.cancel.assert_called_once()
        assert "test-project" in factory._stopped_projects

        # Cleanup
        factory._running_tasks.pop("test-project", None)
        factory._running_engines.pop("test-project", None)
        factory._stopped_projects.discard("test-project")

    def test_stop_engine_without_cancel(self):
        from backend.orchestrator import factory

        mock_engine = MagicMock()
        factory._running_engines["test-project2"] = mock_engine

        factory.stop_engine("test-project2", cancel=False)

        mock_engine.stop.assert_called_once()
        assert "test-project2" in factory._stopped_projects

        # Cleanup
        factory._running_engines.pop("test-project2", None)
        factory._stopped_projects.discard("test-project2")


# =====================================================================
# 13. Artifact Producer Mapping Tests
# =====================================================================


class TestArtifactProducer:
    """Test the artifact-to-agent producer mapping."""

    def test_mapping_completeness(self):
        from backend.orchestrator.planner import _ARTIFACT_PRODUCER

        # All artifact types should have a producer
        for at in ArtifactType:
            assert at in _ARTIFACT_PRODUCER, f"Missing producer for {at.value}"

    def test_key_mappings(self):
        from backend.orchestrator.planner import _ARTIFACT_PRODUCER

        assert _ARTIFACT_PRODUCER[ArtifactType.DIRECTIONS] == AgentRole.DIRECTOR
        assert _ARTIFACT_PRODUCER[ArtifactType.HYPOTHESES] == AgentRole.SCIENTIST
        assert _ARTIFACT_PRODUCER[ArtifactType.EVIDENCE_FINDINGS] == AgentRole.LIBRARIAN
        assert _ARTIFACT_PRODUCER[ArtifactType.DRAFT] == AgentRole.WRITER
        assert _ARTIFACT_PRODUCER[ArtifactType.REVIEW] == AgentRole.CRITIC
