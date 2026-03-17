"""Tests for the Evaluation Engine and Benchmark Framework."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.types import (
    AgentRole,
    ArtifactMeta,
    ArtifactType,
    BenchmarkResult,
    BenchmarkTask,
    Claim,
    Contradiction,
    DimensionScore,
    InformationGainMetric,
    PhaseEvaluation,
    ResearchPhase,
)

# =====================================================================
# 1. Computable Metrics Tests
# =====================================================================


class TestComputableMetrics:
    """Test pure Python computable metrics."""

    def test_coverage_breadth_full(self):
        from backend.evaluation.metrics import coverage_breadth

        artifacts = ["transformer attention mechanism for computer vision"]
        subtopics = ["transformer", "attention", "vision"]
        result = coverage_breadth(artifacts, subtopics)
        assert result.computable_value is not None
        assert result.computable_value == 1.0

    def test_coverage_breadth_partial(self):
        from backend.evaluation.metrics import coverage_breadth

        artifacts = ["transformer model architecture"]
        subtopics = ["transformer", "attention", "vision", "detection"]
        result = coverage_breadth(artifacts, subtopics)
        assert result.computable_value is not None
        assert 0.0 < result.computable_value < 1.0

    def test_coverage_breadth_chinese(self):
        from backend.evaluation.metrics import coverage_breadth

        artifacts = ["大语言模型的推理优化研究"]
        subtopics = ["大语言模型", "推理", "优化"]
        result = coverage_breadth(artifacts, subtopics)
        assert result.computable_value is not None
        assert result.computable_value > 0.0

    def test_coverage_breadth_empty(self):
        from backend.evaluation.metrics import coverage_breadth

        result = coverage_breadth([], [])
        assert result.computable_value == 0.0

    def test_source_diversity_diverse(self):
        from backend.evaluation.metrics import source_diversity

        artifacts = [
            "Reference: https://arxiv.org/abs/2010.11929",
            "Reference: https://dl.acm.org/doi/10.1145/123",
            "Reference: https://openreview.net/forum?id=abc",
        ]
        result = source_diversity(artifacts)
        assert result.computable_value is not None
        assert result.computable_value > 0.5

    def test_source_diversity_single(self):
        from backend.evaluation.metrics import source_diversity

        artifacts = [
            "https://arxiv.org/abs/001",
            "https://arxiv.org/abs/002",
        ]
        result = source_diversity(artifacts)
        assert result.computable_value is not None
        assert result.computable_value == 0.0  # single domain → entropy 0

    def test_structural_completeness_complete(self):
        from backend.evaluation.metrics import structural_completeness

        draft = (
            "# Abstract\nSome text\n# Introduction\nIntro text\n"
            "# Background\nBG\n# Method\nMethods\n# Result\nResults\n"
            "# Discussion\nDisc\n# Conclusion\nConc\n# Reference\nRefs"
        )
        result = structural_completeness(draft)
        assert result.computable_value is not None
        assert result.computable_value == 1.0

    def test_structural_completeness_missing(self):
        from backend.evaluation.metrics import structural_completeness

        draft = "# Abstract\nSome text\n# Introduction\nIntro text"
        result = structural_completeness(draft)
        assert result.computable_value is not None
        assert 0.0 < result.computable_value < 1.0

    def test_structural_completeness_chinese(self):
        from backend.evaluation.metrics import structural_completeness

        draft = (
            "# 摘要\n内容\n# 引言\n内容\n# 背景\n内容\n# 方法\n内容\n"
            "# 结果\n内容\n# 讨论\n内容\n# 结论\n内容\n# 参考\n文献"
        )
        result = structural_completeness(draft)
        assert result.computable_value is not None
        assert result.computable_value == 1.0

    def test_citation_density_high(self):
        from backend.evaluation.metrics import citation_density

        artifacts = [
            "Study [1] showed X. Another work [2] found Y. "
            "Smith et al. (2020) confirmed Z. Reference [3] supports this. "
            "Additional evidence [4] and [5] from doi:10.123/abc."
        ]
        result = citation_density(artifacts)
        assert result.computable_value is not None
        assert result.computable_value > 0.3

    def test_citation_density_none(self):
        from backend.evaluation.metrics import citation_density

        artifacts = ["This is plain text without any citations or references."]
        result = citation_density(artifacts)
        assert result.computable_value is not None
        assert result.computable_value == 0.0

    def test_internal_consistency_clean(self):
        from backend.evaluation.metrics import internal_consistency_keyword

        artifacts = [
            "Transformers are effective for NLP tasks.",
            "Attention mechanisms enable parallel processing.",
        ]
        result = internal_consistency_keyword(artifacts)
        assert result.computable_value is not None
        assert result.computable_value >= 0.8

    def test_internal_consistency_contradictory(self):
        from backend.evaluation.metrics import internal_consistency_keyword

        artifacts = [
            "The results contradict previous findings about efficiency.",
            "There is a 矛盾 between the two methods discussed.",
            "The approaches are 不一致 in their conclusions.",
        ]
        result = internal_consistency_keyword(artifacts)
        assert result.computable_value is not None
        assert result.computable_value < 0.8

    def test_jaccard_identical(self):
        from backend.evaluation.metrics import jaccard_similarity

        assert jaccard_similarity("hello world foo", "hello world foo") == 1.0

    def test_jaccard_disjoint(self):
        from backend.evaluation.metrics import jaccard_similarity

        assert jaccard_similarity("hello world", "foo bar") == 0.0

    def test_jaccard_partial(self):
        from backend.evaluation.metrics import jaccard_similarity

        result = jaccard_similarity("hello world foo", "hello world bar")
        assert 0.0 < result < 1.0


# =====================================================================
# 2. Claim Extractor Tests
# =====================================================================


class TestClaimExtractor:
    """Test LLM-based claim extraction."""

    @pytest.mark.asyncio
    async def test_extract_basic_claims(self):
        from backend.evaluation.claims import ClaimExtractor

        mock_router = AsyncMock()
        mock_router.generate = AsyncMock(
            return_value=json.dumps(
                {
                    "claims": [
                        {
                            "text": "Transformers outperform RNNs",
                            "type": "comparative",
                            "confidence": "strong",
                        },
                        {
                            "text": "Attention is O(n²)",
                            "type": "factual",
                            "confidence": "strong",
                        },
                    ]
                }
            )
        )

        extractor = ClaimExtractor(mock_router, model="test-model")
        claims = await extractor.extract("Some content", "art-001", "evidence_findings")
        assert len(claims) == 2
        assert claims[0].text == "Transformers outperform RNNs"
        assert claims[0].claim_type == "comparative"
        assert claims[0].source_artifact == "evidence_findings/art-001"

    @pytest.mark.asyncio
    async def test_extract_chinese_claims(self):
        from backend.evaluation.claims import ClaimExtractor

        mock_router = AsyncMock()
        mock_router.generate = AsyncMock(
            return_value=json.dumps(
                {
                    "claims": [
                        {
                            "text": "大语言模型在推理任务上表现优异",
                            "type": "factual",
                            "confidence": "moderate",
                        }
                    ]
                }
            )
        )

        extractor = ClaimExtractor(mock_router)
        claims = await extractor.extract("中文内容", "art-002")
        assert len(claims) == 1
        assert "大语言模型" in claims[0].text

    @pytest.mark.asyncio
    async def test_handle_malformed_response(self):
        from backend.evaluation.claims import ClaimExtractor

        mock_router = AsyncMock()
        mock_router.generate = AsyncMock(return_value="This is not JSON at all")

        extractor = ClaimExtractor(mock_router)
        claims = await extractor.extract("content", "art-003")
        assert claims == []

    @pytest.mark.asyncio
    async def test_handle_llm_exception(self):
        from backend.evaluation.claims import ClaimExtractor

        mock_router = AsyncMock()
        mock_router.generate = AsyncMock(side_effect=RuntimeError("API error"))

        extractor = ClaimExtractor(mock_router)
        claims = await extractor.extract("content", "art-004")
        assert claims == []


# =====================================================================
# 3. Contradiction Detector Tests
# =====================================================================


class TestContradictionDetector:
    """Test keyword and LLM contradiction detection."""

    def _make_claim(self, text: str, claim_id: str = "") -> Claim:
        return Claim(
            claim_id=claim_id or text[:8],
            text=text,
            source_artifact="test/art",
        )

    def test_keyword_detect_english(self):
        from backend.evaluation.claims import ContradictionDetector

        detector = ContradictionDetector()
        claims = [
            self._make_claim("Large batch training achieves comparable accuracy", "c1"),
            self._make_claim("Large batch training does not achieve comparable accuracy", "c2"),
        ]
        results = detector.detect_keyword(claims)
        assert len(results) >= 1
        assert results[0].detected_by == "keyword"

    def test_keyword_detect_chinese(self):
        from backend.evaluation.claims import ContradictionDetector

        detector = ContradictionDetector()
        claims = [
            self._make_claim("该方法 效果 显著 提升 性能", "c1"),
            self._make_claim("该方法 效果 不 显著 未 提升 性能", "c2"),
        ]
        results = detector.detect_keyword(claims)
        assert len(results) >= 1

    def test_no_false_positives(self):
        from backend.evaluation.claims import ContradictionDetector

        detector = ContradictionDetector()
        claims = [
            self._make_claim("Apples are fruits", "c1"),
            self._make_claim("Bananas are also fruits", "c2"),
        ]
        results = detector.detect_keyword(claims)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_llm_detect(self):
        from backend.evaluation.claims import ContradictionDetector

        mock_router = AsyncMock()
        mock_router.generate = AsyncMock(
            return_value=json.dumps(
                {
                    "is_contradictory": True,
                    "relationship": "contradictory",
                    "explanation": "Direct negation",
                    "severity": 0.9,
                }
            )
        )

        detector = ContradictionDetector(mock_router)
        claims = [
            self._make_claim("Method A is efficient and fast for processing", "c1"),
            self._make_claim("Method A is efficient but slow for processing", "c2"),
        ]
        results = await detector.detect_llm(claims)
        assert len(results) == 1
        assert results[0].detected_by == "llm"
        assert results[0].severity == 0.9

    @pytest.mark.asyncio
    async def test_detect_all_deduplicates(self):
        from backend.evaluation.claims import ContradictionDetector

        mock_router = AsyncMock()
        mock_router.generate = AsyncMock(
            return_value=json.dumps(
                {
                    "is_contradictory": True,
                    "relationship": "contradictory",
                    "explanation": "Negation",
                    "severity": 0.8,
                }
            )
        )

        detector = ContradictionDetector(mock_router)
        claims = [
            self._make_claim("Large batch training achieves good accuracy", "c1"),
            self._make_claim("Large batch training does not achieve good accuracy", "c2"),
        ]
        results = await detector.detect_all(claims)
        # Both keyword and LLM find the same pair; should be deduplicated
        # Keyword finds it, LLM also finds it but dedup keeps keyword version
        pair_count = len(results)
        assert pair_count >= 1
        # Should not have duplicates for the same claim pair
        pairs = [frozenset([r.claim_a.claim_id, r.claim_b.claim_id]) for r in results]
        assert len(pairs) == len(set(pairs))


# =====================================================================
# 4. Information Gain Detector Tests
# =====================================================================


class TestInformationGainDetector:
    """Test information gain tracking and convergence detection."""

    def test_novel_content(self):
        from backend.evaluation.convergence import InformationGainDetector

        detector = InformationGainDetector()
        detector.add_iteration("alpha beta gamma")
        detector.add_iteration("delta epsilon zeta")
        detector.add_iteration("eta theta iota")
        metric = detector.compute()
        assert not metric.is_diminishing
        assert metric.information_gain > 0.0

    def test_repeated_content_diminishing(self):
        from backend.evaluation.convergence import InformationGainDetector

        detector = InformationGainDetector()
        # First iteration establishes baseline
        base = "the quick brown fox jumps over the lazy dog"
        detector.add_iteration(base)
        # Subsequent iterations add almost nothing new
        for i in range(6):
            detector.add_iteration(base)
        metric = detector.compute()
        assert metric.is_diminishing

    def test_exact_repeat_loop(self):
        from backend.evaluation.convergence import InformationGainDetector

        detector = InformationGainDetector()
        text = "exact same content repeated verbatim"
        detector.add_iteration(text)
        detector.add_iteration(text)
        metric = detector.compute()
        assert metric.is_loop_detected

    def test_window_size_respected(self):
        from backend.evaluation.convergence import InformationGainDetector

        detector = InformationGainDetector()
        # Add many novel iterations, then repeated ones
        for i in range(10):
            detector.add_iteration(f"unique content number {i} with special words_{i}")
        # With default window=5, only last 5 matter for diminishing check
        result = detector.detect_diminishing_returns(window=3)
        # Each iteration has unique words, so should not be diminishing
        assert not result

    def test_reset_clears_history(self):
        from backend.evaluation.convergence import InformationGainDetector

        detector = InformationGainDetector()
        detector.add_iteration("some content")
        detector.add_iteration("more content")
        detector.reset()
        metric = detector.compute()
        assert metric.iteration == 0

    def test_single_iteration_safe(self):
        from backend.evaluation.convergence import InformationGainDetector

        detector = InformationGainDetector()
        detector.add_iteration("first iteration content")
        metric = detector.compute()
        assert metric.iteration == 1
        assert metric.information_gain == 1.0
        assert not metric.is_diminishing
        assert not metric.is_loop_detected


# =====================================================================
# 5. Evaluator Service Tests
# =====================================================================


class TestEvaluatorService:
    """Test the main evaluation orchestrator."""

    @pytest.fixture
    def mock_router(self):
        router = AsyncMock()
        router.generate = AsyncMock(
            return_value=json.dumps({"score": 0.7, "evidence": ["Good quality"]})
        )
        return router

    @pytest.fixture
    def evaluator(self, mock_router):
        from backend.evaluation.evaluator import EvaluatorService

        return EvaluatorService(mock_router)

    def test_select_evaluator_model_different(self, evaluator):
        result = evaluator._select_evaluator_model("deepseek-chat")
        assert result != "deepseek-chat"

    def test_select_evaluator_model_deepseek_reasoner(self, evaluator):
        # deepseek-reasoner should try claude first, fall back to deepseek-chat
        result = evaluator._select_evaluator_model("deepseek-reasoner")
        assert result != "deepseek-reasoner"

    @pytest.mark.asyncio
    async def test_evaluate_phase(self, evaluator, tmp_path):
        from backend.blackboard.board import Blackboard

        board = Blackboard(tmp_path)
        await board.init_workspace(research_topic="test topic")

        meta = ArtifactMeta(
            artifact_type=ArtifactType.EVIDENCE_FINDINGS,
            artifact_id="ev-001",
            version=1,
            created_by=AgentRole.SCIENTIST,
        )
        await board.write_artifact(
            ArtifactType.EVIDENCE_FINDINGS,
            "ev-001",
            1,
            "Some evidence about transformers and attention",
            meta,
        )

        result = await evaluator.evaluate_phase(board, ResearchPhase.EXPLORE)
        assert isinstance(result, PhaseEvaluation)
        assert result.phase == ResearchPhase.EXPLORE
        assert len(result.dimensions) > 0
        assert result.composite_score >= 0.0

    @pytest.mark.asyncio
    async def test_save_results(self, evaluator, tmp_path):
        evaluation = PhaseEvaluation(
            phase=ResearchPhase.EXPLORE,
            composite_score=0.75,
            evaluator_model="test-model",
            dimensions={
                "coverage": DimensionScore(name="coverage", combined=0.8),
            },
        )
        path = await evaluator.save_results(tmp_path, evaluation)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["composite_score"] == 0.75

    @pytest.mark.asyncio
    async def test_evaluate_contradictions(self, tmp_path):
        from backend.evaluation.evaluator import EvaluatorService

        mock_router = AsyncMock()
        # First call: claim extraction
        mock_router.generate = AsyncMock(
            return_value=json.dumps(
                {"claims": [{"text": "A is true", "type": "factual", "confidence": "strong"}]}
            )
        )

        evaluator = EvaluatorService(mock_router)
        board = MagicMock()
        board.list_artifacts = AsyncMock(return_value=[])

        result = await evaluator.evaluate_contradictions(board)
        assert isinstance(result, list)

    def test_check_information_gain(self, evaluator):
        metric = evaluator.check_information_gain("New research findings about attention")
        assert isinstance(metric, InformationGainMetric)
        assert metric.iteration == 1


# =====================================================================
# 6. Benchmark Runner Tests
# =====================================================================


class TestBenchmarkRunner:
    """Test benchmark task loading and execution."""

    def test_load_tasks(self):
        from backend.benchmarks.runner import BenchmarkRunner

        mock_evaluator = MagicMock()
        tasks_dir = Path(__file__).parent.parent / "benchmarks" / "tasks"
        runner = BenchmarkRunner(mock_evaluator, tasks_dir=tasks_dir)
        tasks = runner.load_tasks()
        assert len(tasks) == 5
        task_ids = {t.task_id for t in tasks}
        assert "explore_coverage" in task_ids
        assert "contradiction_detection" in task_ids

    @pytest.mark.asyncio
    async def test_run_task(self, tmp_path):
        from backend.benchmarks.runner import BenchmarkRunner
        from backend.evaluation.evaluator import EvaluatorService

        mock_router = AsyncMock()
        mock_router.generate = AsyncMock(
            return_value=json.dumps({"score": 0.7, "evidence": ["OK"]})
        )

        evaluator = EvaluatorService(mock_router)
        runner = BenchmarkRunner(evaluator)

        task = BenchmarkTask(
            task_id="test_task",
            research_topic="Test topic",
            phase="explore",
            input_artifacts=[
                {
                    "artifact_type": "evidence_findings",
                    "artifact_id": "ev-001",
                    "created_by": "scientist",
                    "content": "Test content about transformers",
                }
            ],
        )
        result = await runner.run_task(task)
        assert isinstance(result, BenchmarkResult)
        assert result.task_id == "test_task"
        assert result.evaluation is not None
        assert result.error is None

    @pytest.mark.asyncio
    async def test_setup_temp_board(self, tmp_path):
        from backend.benchmarks.runner import BenchmarkRunner

        mock_evaluator = MagicMock()
        runner = BenchmarkRunner(mock_evaluator)

        task = BenchmarkTask(
            task_id="test",
            research_topic="Test",
            phase="explore",
            input_artifacts=[
                {
                    "artifact_type": "evidence_findings",
                    "artifact_id": "ev-001",
                    "created_by": "scientist",
                    "content": "Test content",
                },
                {
                    "artifact_type": "hypotheses",
                    "artifact_id": "hyp-001",
                    "created_by": "scientist",
                    "content": "Test hypothesis",
                },
            ],
        )
        board = await runner._setup_temp_board(task, tmp_path)
        ev_arts = await board.list_artifacts(ArtifactType.EVIDENCE_FINDINGS)
        hyp_arts = await board.list_artifacts(ArtifactType.HYPOTHESES)
        assert len(ev_arts) == 1
        assert len(hyp_arts) == 1

    def test_ablation_configs_exist(self):
        from backend.benchmarks.runner import ABLATION_PRESETS

        assert "baseline" in ABLATION_PRESETS
        assert "full_system" in ABLATION_PRESETS
        assert "cross_model_only" in ABLATION_PRESETS
        assert "no_computable" in ABLATION_PRESETS
        assert "no_llm_eval" in ABLATION_PRESETS
        # Baseline disables new features
        baseline = ABLATION_PRESETS["baseline"]
        assert not baseline.use_cross_model
        assert not baseline.use_multi_dim
        assert not baseline.use_info_gain


# =====================================================================
# 7. Benchmark Scorer Tests
# =====================================================================


class TestBenchmarkScorer:
    """Test gold standard comparison scoring."""

    def test_score_within_range_passed(self):
        from backend.benchmarks.scorer import BenchmarkScorer

        scorer = BenchmarkScorer()
        result = BenchmarkResult(
            task_id="test",
            evaluation=PhaseEvaluation(
                phase=ResearchPhase.EXPLORE,
                dimensions={
                    "coverage_breadth": DimensionScore(name="coverage_breadth", combined=0.7),
                },
            ),
        )
        task = BenchmarkTask(
            task_id="test",
            research_topic="Test",
            phase="explore",
            expected_evaluation={"coverage_breadth": [0.5, 0.9]},
        )
        scored = scorer.score_result(result, task)
        assert scored.passed is True

    def test_score_outside_range_failed(self):
        from backend.benchmarks.scorer import BenchmarkScorer

        scorer = BenchmarkScorer()
        result = BenchmarkResult(
            task_id="test",
            evaluation=PhaseEvaluation(
                phase=ResearchPhase.EXPLORE,
                dimensions={
                    "coverage_breadth": DimensionScore(name="coverage_breadth", combined=0.2),
                },
            ),
        )
        task = BenchmarkTask(
            task_id="test",
            research_topic="Test",
            phase="explore",
            expected_evaluation={"coverage_breadth": [0.5, 0.9]},
        )
        scored = scorer.score_result(result, task)
        assert scored.passed is False

    def test_contradiction_f1_perfect(self):
        from backend.benchmarks.scorer import BenchmarkScorer

        detected = [
            Contradiction(
                contradiction_id="c1",
                claim_a=Claim(claim_id="a", text="X is true good", source_artifact="t"),
                claim_b=Claim(claim_id="b", text="X is false bad", source_artifact="t"),
            )
        ]
        expected = [{"claim_a": "X is true good", "claim_b": "X is false bad"}]
        p, r, f1 = BenchmarkScorer.contradiction_f1(detected, expected)
        assert f1 == 1.0

    def test_contradiction_f1_zero(self):
        from backend.benchmarks.scorer import BenchmarkScorer

        expected = [{"claim_a": "completely different", "claim_b": "totally unrelated"}]
        p, r, f1 = BenchmarkScorer.contradiction_f1([], expected)
        assert f1 == 0.0

    def test_generate_report_structure(self):
        from backend.benchmarks.scorer import BenchmarkScorer

        results = [
            BenchmarkResult(task_id="t1", passed=True, config_name="baseline"),
            BenchmarkResult(task_id="t2", passed=False, config_name="baseline"),
            BenchmarkResult(task_id="t3", passed=True, config_name="full_system"),
        ]
        report = BenchmarkScorer.generate_report(results)
        assert report["total"] == 3
        assert report["passed"] == 2
        assert report["failed"] == 1
        assert "baseline" in report["by_config"]
        assert "full_system" in report["by_config"]
        assert report["by_config"]["baseline"]["total"] == 2
        assert len(report["task_results"]) == 3


# =====================================================================
# 8. Dimensions Tests
# =====================================================================


class TestDimensions:
    """Test dimension definitions."""

    def test_get_dimensions_explore(self):
        from backend.evaluation.dimensions import get_dimensions

        dims = get_dimensions(ResearchPhase.EXPLORE)
        assert len(dims) == 4
        weights = [w for _, _, w in dims]
        assert abs(sum(weights) - 1.0) < 0.01

    def test_get_dimensions_compose(self):
        from backend.evaluation.dimensions import get_dimensions

        dims = get_dimensions(ResearchPhase.COMPOSE)
        assert len(dims) == 4
        dim_names = [d.value if hasattr(d, "value") else d for d, _, _ in dims]
        assert "structural_completeness" in dim_names

    def test_get_dimensions_fallback(self):
        from backend.evaluation.dimensions import get_dimensions

        # COMPLETE phase not in map, should fallback to EXPLORE
        dims = get_dimensions(ResearchPhase.COMPLETE)
        assert len(dims) > 0

    def test_all_phases_weights_sum_to_one(self):
        from backend.evaluation.dimensions import PHASE_DIMENSIONS

        for phase, dims in PHASE_DIMENSIONS.items():
            total = sum(w for _, _, w in dims)
            assert abs(total - 1.0) < 0.01, f"Phase {phase} weights sum to {total}"


# =====================================================================
# 9. Evidence Mapping Tests
# =====================================================================


class TestEvidenceMapping:
    """Test the evidence_mapping computable metric."""

    def test_all_hypotheses_mapped(self):
        from backend.evaluation.metrics import evidence_mapping

        hypotheses = [
            "Transformer models improve performance on vision tasks",
            "Attention mechanism reduces computational overhead",
        ]
        evidence = [
            "Studies show transformer models significantly improve performance on vision tasks "
            "through better feature extraction mechanisms.",
            "The attention mechanism reduces computational overhead compared to "
            "recurrent approaches in multiple benchmarks.",
        ]
        result = evidence_mapping(hypotheses, evidence)
        assert result.computable_value == 1.0

    def test_partial_mapping(self):
        from backend.evaluation.metrics import evidence_mapping

        hypotheses = [
            "Transformer models improve performance on vision tasks",
            "Quantum computing will revolutionize cryptography",
        ]
        evidence = [
            "Transformer models show strong performance on vision tasks with better accuracy.",
        ]
        result = evidence_mapping(hypotheses, evidence)
        assert 0.0 < result.computable_value < 1.0

    def test_no_hypotheses(self):
        from backend.evaluation.metrics import evidence_mapping

        result = evidence_mapping([], ["some evidence text"])
        assert result.computable_value == 0.0


# =====================================================================
# 10. Specificity Tests
# =====================================================================


class TestSpecificity:
    """Test the specificity computable metric."""

    def test_high_specificity(self):
        from backend.evaluation.metrics import specificity

        artifacts = [
            "The model achieved 95.3% accuracy on ImageNet with 12.5M parameters. "
            "Training took 48 hours on 8 A100 GPUs with a batch size of 256. "
            "The learning rate was 0.001 with AdamW optimizer. "
            "Results: 92.1% top-1, 98.7% top-5 accuracy."
        ]
        result = specificity(artifacts)
        assert result.computable_value is not None
        assert result.computable_value > 0.3

    def test_low_specificity(self):
        from backend.evaluation.metrics import specificity

        artifacts = [
            "The approach showed good results and performed well across tasks. "
            "The method is effective and can be applied to various domains. "
            "Overall the system works as expected and meets requirements."
        ]
        result = specificity(artifacts)
        assert result.computable_value is not None
        assert result.computable_value < 0.3

    def test_chinese_with_numbers(self):
        from backend.evaluation.metrics import specificity

        artifacts = [
            "该模型在测试集上达到了95.3%的准确率，参数量为12.5M。"
            "训练耗时48小时，使用8张A100 GPU，批次大小为256。"
        ]
        result = specificity(artifacts)
        assert result.computable_value is not None
        assert result.computable_value > 0.0


# =====================================================================
# 11. Claim Store Tests
# =====================================================================


class TestClaimStore:
    """Test ClaimStore DB persistence (mocked session)."""

    def test_confidence_mapping_values(self):
        from backend.evaluation.store import _CONFIDENCE_MAP

        assert _CONFIDENCE_MAP["strong"] == 1.0
        assert _CONFIDENCE_MAP["moderate"] == 0.7
        assert _CONFIDENCE_MAP["tentative"] == 0.4

    def test_confidence_mapping(self):
        from backend.evaluation.store import _CONFIDENCE_MAP

        assert _CONFIDENCE_MAP["strong"] == 1.0
        assert _CONFIDENCE_MAP["moderate"] == 0.7
        assert _CONFIDENCE_MAP["tentative"] == 0.4
        assert "unknown" not in _CONFIDENCE_MAP

    def test_empty_claims_returns_empty(self):
        """Verify save_claims with empty list short-circuits."""
        import asyncio

        from backend.evaluation.store import ClaimStore

        result = asyncio.get_event_loop().run_until_complete(
            ClaimStore.save_claims("12345678-1234-1234-1234-123456789012", [])
        )
        assert result == []

    def test_store_classes_exist(self):
        from backend.evaluation.store import ClaimStore, ContradictionStore, EvaluationStore

        assert hasattr(ClaimStore, "save_claims")
        assert hasattr(ClaimStore, "load_claims")
        assert hasattr(ContradictionStore, "save_contradictions")
        assert hasattr(ContradictionStore, "load_contradictions")
        assert hasattr(EvaluationStore, "save_evaluation")
        assert hasattr(EvaluationStore, "save_iteration_metric")


# =====================================================================
# 12. Evaluation Store Tests
# =====================================================================


class TestEvaluationStore:
    """Test EvaluationStore structure and interface."""

    def test_save_evaluation_signature(self):
        import inspect

        from backend.evaluation.store import EvaluationStore

        sig = inspect.signature(EvaluationStore.save_evaluation)
        params = list(sig.parameters.keys())
        assert "project_id" in params
        assert "evaluation" in params
        assert "iteration" in params

    def test_save_iteration_metric_signature(self):
        import inspect

        from backend.evaluation.store import EvaluationStore

        sig = inspect.signature(EvaluationStore.save_iteration_metric)
        params = list(sig.parameters.keys())
        assert "project_id" in params
        assert "phase" in params
        assert "iteration" in params
        assert "metric" in params
        assert "eval_composite" in params

    def test_empty_contradictions_returns_empty(self):
        """Verify save_contradictions with empty list short-circuits."""
        import asyncio

        from backend.evaluation.store import ContradictionStore

        result = asyncio.get_event_loop().run_until_complete(
            ContradictionStore.save_contradictions("12345678-1234-1234-1234-123456789012", [], {})
        )
        assert result == []


# =====================================================================
# 13. Contradiction Store Tests
# =====================================================================


class TestContradictionStore:
    """Test ContradictionStore structure."""

    def test_evidence_encoding(self):
        """Verify that evidence JSON encodes relationship and detected_by."""
        import json as json_mod

        evidence_json = json_mod.dumps(
            {
                "explanation": "Direct negation",
                "relationship": "contradictory",
                "detected_by": "keyword",
            },
            ensure_ascii=False,
        )
        parsed = json_mod.loads(evidence_json)
        assert parsed["relationship"] == "contradictory"
        assert parsed["detected_by"] == "keyword"
        assert parsed["explanation"] == "Direct negation"

    def test_evaluator_with_project_id(self):
        """Test that EvaluatorService accepts project_id."""
        from backend.evaluation.evaluator import EvaluatorService

        mock_router = AsyncMock()
        evaluator = EvaluatorService(mock_router, project_id="test-project-id")
        assert evaluator._project_id == "test-project-id"


# =====================================================================
# 14. Store DB Round-Trip Tests (N02 fix)
# =====================================================================


class TestClaimStoreRoundTrip:
    """Test ClaimStore with mocked DB session to verify ORM column mapping."""

    @pytest.mark.asyncio
    async def test_save_claims_orm_mapping(self):
        """Verify Pydantic Claim → ORM Claim column mapping."""
        from unittest.mock import patch

        from backend.evaluation.store import ClaimStore

        captured_rows = []

        mock_session = AsyncMock()
        mock_session.add = MagicMock(side_effect=lambda row: captured_rows.append(row))
        mock_session.begin = MagicMock(return_value=AsyncMock())
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx)

        claims = [
            Claim(
                claim_id="c1",
                text="LLMs can reason about code",
                source_artifact="hypothesis_001",
                confidence="strong",
            ),
            Claim(
                claim_id="c2",
                text="Transformers struggle with arithmetic",
                source_artifact="evidence_002",
                confidence="tentative",
            ),
        ]

        with patch("backend.models.async_session_factory", mock_factory):
            ids = await ClaimStore.save_claims(
                "12345678-1234-1234-1234-123456789012", claims,
            )

        assert len(ids) == 2
        assert len(captured_rows) == 2

        # Verify ORM field mapping
        row0 = captured_rows[0]
        assert row0.text == "LLMs can reason about code"
        assert row0.confidence == 1.0  # "strong" → 1.0
        assert row0.source_agent == "hypothesis_001"  # source_artifact → source_agent

        row1 = captured_rows[1]
        assert row1.text == "Transformers struggle with arithmetic"
        assert row1.confidence == 0.4  # "tentative" → 0.4
        assert row1.source_agent == "evidence_002"

    @pytest.mark.asyncio
    async def test_load_claims_reverse_mapping(self):
        """Verify ORM Claim → Pydantic Claim reverse mapping."""
        import uuid
        from unittest.mock import patch

        from backend.evaluation.store import ClaimStore

        # Create mock ORM rows
        mock_row1 = MagicMock()
        mock_row1.id = uuid.uuid4()
        mock_row1.text = "Test claim text"
        mock_row1.confidence = 1.0
        mock_row1.source_agent = "hyp_001"
        mock_row1.created_at = None

        mock_row2 = MagicMock()
        mock_row2.id = uuid.uuid4()
        mock_row2.text = "Another claim"
        mock_row2.confidence = 0.4
        mock_row2.source_agent = None
        mock_row2.created_at = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_row1, mock_row2]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx)

        with patch("backend.models.async_session_factory", mock_factory):
            claims = await ClaimStore.load_claims(
                "12345678-1234-1234-1234-123456789012",
            )

        assert len(claims) == 2
        assert claims[0].text == "Test claim text"
        assert claims[0].confidence == "strong"  # 1.0 → "strong"
        assert claims[0].source_artifact == "hyp_001"
        assert claims[1].confidence == "tentative"  # 0.4 → "tentative"
        assert claims[1].source_artifact == ""  # None → ""


class TestContradictionStoreRoundTrip:
    """Test ContradictionStore ORM mapping with mocked session."""

    @pytest.mark.asyncio
    async def test_save_contradictions_orm_mapping(self):
        """Verify Pydantic Contradiction → ORM Contradiction mapping."""
        import uuid
        from unittest.mock import patch

        from backend.evaluation.store import ContradictionStore

        captured_rows = []

        mock_session = AsyncMock()
        mock_session.add = MagicMock(side_effect=lambda row: captured_rows.append(row))
        mock_session.begin = MagicMock(return_value=AsyncMock())
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx)

        claim_a = Claim(
            claim_id="c1", text="Claim A", source_artifact="a", confidence="strong",
        )
        claim_b = Claim(
            claim_id="c2", text="Claim B", source_artifact="b", confidence="moderate",
        )
        contradiction = Contradiction(
            contradiction_id="ct1",
            claim_a=claim_a,
            claim_b=claim_b,
            relationship="contradictory",
            explanation="Direct negation",
            severity=0.8,
            detected_by="keyword",
        )

        uuid_a = uuid.uuid4()
        uuid_b = uuid.uuid4()
        claim_id_map = {"c1": uuid_a, "c2": uuid_b}

        with patch("backend.models.async_session_factory", mock_factory):
            ids = await ContradictionStore.save_contradictions(
                "12345678-1234-1234-1234-123456789012",
                [contradiction],
                claim_id_map,
            )

        assert len(ids) == 1
        assert len(captured_rows) == 1

        row = captured_rows[0]
        assert row.claim_a_id == uuid_a
        assert row.claim_b_id == uuid_b
        assert row.confidence == 0.8  # severity → confidence
        assert row.status == "detected"

        # Verify evidence JSON serialization
        import json as json_mod

        evidence = json_mod.loads(row.evidence)
        assert evidence["explanation"] == "Direct negation"
        assert evidence["relationship"] == "contradictory"
        assert evidence["detected_by"] == "keyword"

    @pytest.mark.asyncio
    async def test_skips_missing_claim_uuid(self):
        """Contradictions with unmapped claim IDs should be skipped."""
        from unittest.mock import patch

        from backend.evaluation.store import ContradictionStore

        captured_rows = []

        mock_session = AsyncMock()
        mock_session.add = MagicMock(side_effect=lambda row: captured_rows.append(row))
        mock_session.begin = MagicMock(return_value=AsyncMock())
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx)

        claim_a = Claim(claim_id="c1", text="A", source_artifact="x")
        claim_b = Claim(claim_id="c_missing", text="B", source_artifact="y")
        contradiction = Contradiction(
            contradiction_id="ct1",
            claim_a=claim_a,
            claim_b=claim_b,
            explanation="test",
        )

        # Only c1 is mapped, c_missing is not
        import uuid

        claim_id_map = {"c1": uuid.uuid4()}

        with patch("backend.models.async_session_factory", mock_factory):
            ids = await ContradictionStore.save_contradictions(
                "12345678-1234-1234-1234-123456789012",
                [contradiction],
                claim_id_map,
            )

        assert len(ids) == 0
        assert len(captured_rows) == 0


class TestEvaluationStoreRoundTrip:
    """Test EvaluationStore ORM mapping with mocked session."""

    @pytest.mark.asyncio
    async def test_save_evaluation_orm_mapping(self):
        """Verify PhaseEvaluation → EvaluationResult ORM mapping."""
        from unittest.mock import patch

        from backend.evaluation.store import EvaluationStore

        captured_rows = []

        mock_session = AsyncMock()
        mock_session.add = MagicMock(side_effect=lambda row: captured_rows.append(row))
        mock_session.begin = MagicMock(return_value=AsyncMock())
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx)

        evaluation = PhaseEvaluation(
            phase=ResearchPhase.EXPLORE,
            dimensions={
                "coverage": DimensionScore(
                    name="coverage",
                    weight=0.3,
                    computable_value=0.8,
                    combined=0.8,
                    evidence=["High coverage"],
                ),
            },
            composite_score=0.75,
            evaluator_model="deepseek-chat",
            evaluator_provider="deepseek",
            raw_evidence={"test": "data"},
        )

        with patch("backend.models.async_session_factory", mock_factory):
            row_id = await EvaluationStore.save_evaluation(
                "12345678-1234-1234-1234-123456789012", evaluation, iteration=3,
            )

        assert row_id is not None
        assert len(captured_rows) == 1

        row = captured_rows[0]
        assert row.phase == "explore"
        assert row.iteration == 3
        assert row.composite_score == 0.75
        assert row.evaluator_model == "deepseek-chat"
        assert row.evaluator_provider == "deepseek"
        assert row.raw_evidence == {"test": "data"}
        assert "coverage" in row.dimensions

    @pytest.mark.asyncio
    async def test_save_iteration_metric_orm_mapping(self):
        """Verify InformationGainMetric → IterationMetric ORM mapping."""
        from unittest.mock import patch

        from backend.evaluation.store import EvaluationStore

        captured_rows = []

        mock_session = AsyncMock()
        mock_session.add = MagicMock(side_effect=lambda row: captured_rows.append(row))
        mock_session.begin = MagicMock(return_value=AsyncMock())
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx)

        metric = InformationGainMetric(
            iteration=5,
            information_gain=0.12,
            artifact_count_delta=3,
            unique_claim_delta=2,
            is_diminishing=True,
            is_loop_detected=False,
        )

        with patch("backend.models.async_session_factory", mock_factory):
            row_id = await EvaluationStore.save_iteration_metric(
                "12345678-1234-1234-1234-123456789012",
                phase="explore",
                iteration=5,
                metric=metric,
                eval_composite=0.65,
            )

        assert row_id is not None
        assert len(captured_rows) == 1

        row = captured_rows[0]
        assert row.phase == "explore"
        assert row.iteration == 5
        assert row.information_gain == 0.12
        assert row.artifact_count_delta == 3
        assert row.unique_claim_delta == 2
        assert row.eval_composite == 0.65
        assert row.metrics["is_diminishing"] is True
        assert row.metrics["is_loop_detected"] is False
