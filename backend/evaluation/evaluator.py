"""EvaluatorService -- cross-model orchestrator for multi-dimensional evaluation."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from backend.config import settings
from backend.evaluation.claims import ClaimExtractor, ContradictionDetector
from backend.evaluation.convergence import InformationGainDetector
from backend.evaluation.dimensions import get_dimensions
from backend.evaluation.metrics import (
    citation_density,
    coverage_breadth,
    evidence_mapping,
    internal_consistency_keyword,
    source_diversity,
    specificity,
    structural_completeness,
    terminology_coverage,
)
from backend.types import (
    ArtifactType,
    Claim,
    ContextLevel,
    Contradiction,
    DimensionScore,
    EvaluationDimension,
    InformationGainMetric,
    PhaseEvaluation,
    ResearchPhase,
)
from backend.utils.json_utils import safe_json_loads
from backend.utils.nlp import tokenize_topic as _tokenize_topic

if TYPE_CHECKING:
    from backend.blackboard.board import Blackboard
    from backend.llm.router import LLMRouter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# D06: Cross-model mapping: generator -> evaluator (complete matrix)
# ---------------------------------------------------------------------------
_CROSS_MODEL_MAP: dict[str, str] = {
    "deepseek-reasoner": "claude-sonnet-4-6",
    "deepseek-chat": "deepseek-reasoner",
    "claude-opus-4-6": "deepseek-reasoner",
    "claude-sonnet-4-6": "deepseek-reasoner",
}

# ---------------------------------------------------------------------------
# D05: Dimension-specific evaluation criteria
# ---------------------------------------------------------------------------
_DIMENSION_CRITERIA: dict[str, str] = {
    "coverage_breadth": (
        "Assess how thoroughly the artifacts cover the research topic space. "
        "Look for breadth of subtopics, perspectives, and methodological approaches."
    ),
    "source_diversity": (
        "Evaluate the variety and quality of information sources referenced. "
        "Consider academic papers, datasets, tools, and cross-domain references."
    ),
    "terminology_coverage": (
        "Check whether key domain-specific terms, acronyms, and concepts are "
        "correctly identified and consistently used throughout the artifacts."
    ),
    "gap_identification": (
        "Assess whether the artifacts explicitly identify knowledge gaps, open "
        "questions, and under-explored areas within the research topic."
    ),
    "specificity": (
        "Evaluate how precise and actionable the hypotheses or claims are. "
        "Vague or overly broad statements should score lower."
    ),
    "novelty": (
        "Judge whether the artifacts introduce original insights, novel "
        "combinations, or non-obvious connections beyond surface-level synthesis."
    ),
    "logical_coherence": (
        "Check that arguments follow logically, premises support conclusions, "
        "and there are no contradictions or unsupported leaps in reasoning."
    ),
    "citation_density": (
        "Measure the frequency and appropriateness of citations. Evidence claims "
        "should be backed by specific references rather than unsupported assertions."
    ),
    "evidence_mapping": (
        "Assess whether each hypothesis or claim is explicitly linked to "
        "supporting or contradicting evidence with clear traceability."
    ),
    "methodological_rigor": (
        "Evaluate whether the research methods described are sound, reproducible, "
        "and appropriate for the stated research questions."
    ),
    "structural_completeness": (
        "Check that the composition includes all expected sections (introduction, "
        "background, methods, results, discussion, conclusion) with adequate depth."
    ),
    "argument_flow": (
        "Evaluate the logical progression from introduction through evidence to "
        "conclusions. Transitions should be smooth and the narrative coherent."
    ),
    "citation_integration": (
        "Assess how well citations are woven into the narrative. Citations should "
        "support specific claims rather than appear as disconnected lists."
    ),
    "internal_consistency": (
        "Check for contradictions between different sections or artifacts. "
        "Terminology, data, and conclusions should be consistent throughout."
    ),
}

_LLM_EVAL_PROMPT = """\
You are evaluating research artifacts on dimension: **{dimension}** (Phase: {phase}).

## Evaluation Criteria
{criteria}

## Scoring Scale
- 0.0-0.2: Critical gaps, major issues
- 0.3-0.5: Partial coverage, notable weaknesses
- 0.5-0.7: Adequate, meets basic expectations
- 0.7-0.9: Strong, well-developed
- 0.9-1.0: Exceptional, comprehensive

## Scoring Constraints
- Score > 0.7 requires at least 3 positive findings
- Score < 0.3 requires at least 2 identified missing items

Return a JSON object:
{{"score": <float 0.0-1.0>, "evidence": [{{"finding": "...", "artifact_ref": "...", \
"impact": "positive|negative|neutral"}}], "missing": ["item1", "item2"]}}

## Artifacts to Evaluate
{artifacts}
"""


class EvaluatorService:
    """Main orchestrator for multi-dimensional evaluation."""

    def __init__(
        self,
        llm_router: LLMRouter,
        claim_extractor: ClaimExtractor | None = None,
        contradiction_detector: ContradictionDetector | None = None,
        info_gain: InformationGainDetector | None = None,
        project_id: str | None = None,
        embedding_service: object | None = None,
    ) -> None:
        self._router = llm_router
        self._claim_extractor = claim_extractor or ClaimExtractor(
            llm_router, embedding_service=embedding_service,
        )
        self._contradiction_detector = contradiction_detector or ContradictionDetector(llm_router)
        self._info_gain = info_gain or InformationGainDetector()
        self._project_id = project_id

    async def evaluate_phase(
        self,
        board: Blackboard,
        phase: ResearchPhase,
        generator_model: str = "",
        evaluator_model: str | None = None,
        *,
        iteration: int = 0,
        use_cross_model: bool = True,
        use_multi_dim: bool = True,
        use_computable: bool = True,
        use_llm_eval: bool = True,
    ) -> PhaseEvaluation:
        """Run full multi-dimensional evaluation for a research phase.

        Ablation flags control which evaluation components are active:
        - use_cross_model: use a different model for evaluation vs generation
        - use_multi_dim: evaluate per-dimension (False = single overall score)
        - use_computable: run computable metrics
        - use_llm_eval: run LLM-based evaluation
        """
        if use_cross_model:
            use_evaluator = evaluator_model or self._select_evaluator_model(generator_model)
        else:
            use_evaluator = evaluator_model or settings.eval_model

        # Collect artifacts (flat list + by-type for evidence_mapping)
        artifact_texts = await self._collect_artifacts(board)
        artifacts_by_type = await self._collect_artifacts_by_type(board)
        subtopics = await self._extract_subtopics(board)

        eval_result = PhaseEvaluation(
            phase=phase,
            evaluator_model=use_evaluator,
            timestamp=datetime.now(UTC),
        )

        # Single-dimension mode: skip per-dimension loop, do one overall LLM call
        if not use_multi_dim:
            if use_llm_eval:
                overall = await self._evaluate_dimension_llm(
                    "overall_quality", artifact_texts, phase, use_evaluator
                )
                eval_result.composite_score = overall.llm_value or 0.0
                eval_result.dimensions["overall_quality"] = overall
            elif use_computable:
                # Fallback: use coverage_breadth as a single computable proxy
                score = self._compute_metric(
                    "coverage_breadth", artifact_texts, subtopics, artifacts_by_type
                )
                eval_result.composite_score = score.computable_value or 0.0
                eval_result.dimensions["coverage_breadth"] = score
            return eval_result

        dimensions = get_dimensions(phase)
        total_weight = 0.0
        weighted_sum = 0.0

        for dim_name, eval_type, weight in dimensions:
            dim_key = dim_name.value if isinstance(dim_name, EvaluationDimension) else dim_name
            score = DimensionScore(name=dim_key, weight=weight)

            if use_computable and eval_type in ("computable", "mixed"):
                score = self._compute_metric(dim_key, artifact_texts, subtopics, artifacts_by_type)
                score.weight = weight

            if use_llm_eval and eval_type in ("llm", "mixed"):
                llm_score = await self._evaluate_dimension_llm(
                    dim_key, artifact_texts, phase, use_evaluator
                )
                if eval_type == "mixed" and use_computable and score.computable_value is not None:
                    score.llm_value = llm_score.llm_value
                    comp_w = settings.eval_computable_weight
                    llm_w = settings.eval_llm_weight
                    comp_val = score.computable_value or 0.0
                    llm_val = llm_score.llm_value or 0.0
                    score.combined = comp_w * comp_val + llm_w * llm_val
                else:
                    score = llm_score
                    score.weight = weight
                    score.combined = llm_score.llm_value or 0.0
            elif not use_llm_eval and eval_type in ("llm",):
                # LLM eval disabled, skip pure-LLM dimensions
                score.combined = 0.0

            if eval_type == "computable" and use_computable:
                score.combined = score.computable_value or 0.0
            elif eval_type == "computable" and not use_computable:
                score.combined = 0.0

            eval_result.dimensions[dim_key] = score
            weighted_sum += score.combined * weight
            total_weight += weight

        eval_result.composite_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Persist to DB if project_id is set
        if self._project_id:
            await self._save_evaluation_to_db(eval_result, iteration=iteration)

        return eval_result

    async def evaluate_contradictions(
        self,
        board: Blackboard,
        types: list[ArtifactType] | None = None,
    ) -> list[Contradiction]:
        """Extract claims from board artifacts and detect contradictions."""
        target_types = types or [
            ArtifactType.EVIDENCE_FINDINGS,
            ArtifactType.HYPOTHESES,
            ArtifactType.DIRECTIONS,
        ]
        all_claims: list[Claim] = []
        for art_type in target_types:
            metas = await board.list_artifacts(art_type)
            for m in metas:
                ver = await board.get_latest_version(art_type, m.artifact_id)
                if ver == 0:
                    continue
                content = await board.read_artifact(art_type, m.artifact_id, ver, ContextLevel.L2)
                if not content:
                    continue
                text = content if isinstance(content, str) else json.dumps(content)
                claims = await self._claim_extractor.extract(text, m.artifact_id, art_type.value)
                all_claims.extend(claims)

        contradictions = await self._contradiction_detector.detect_all(all_claims)

        # Persist claims and contradictions to DB
        if self._project_id and (all_claims or contradictions):
            await self._save_claims_to_db(all_claims, contradictions)

        return contradictions

    def check_information_gain(self, content: str) -> InformationGainMetric:
        """Add iteration content and compute information gain."""
        self._info_gain.add_iteration(content)
        return self._info_gain.compute()

    async def save_results(self, project_path: Path, evaluation: PhaseEvaluation) -> Path:
        """Save evaluation results as JSON to project eval_results directory."""
        eval_dir = project_path / "eval_results"
        eval_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{evaluation.phase.value}_{evaluation.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        path = eval_dir / filename

        data = evaluation.model_dump(mode="json")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Saved evaluation results to %s", path)
        return path

    def _select_evaluator_model(self, generator_model: str) -> str:
        """Select an evaluator model different from the generator."""
        if not settings.eval_cross_model:
            return settings.eval_model

        # Check cross-model map
        evaluator = _CROSS_MODEL_MAP.get(generator_model)
        if evaluator:
            # Verify the evaluator's provider key is available
            if evaluator.startswith("claude-") and settings.anthropic_api_key:
                return evaluator
            if evaluator.startswith("deepseek-") and settings.deepseek_api_key:
                return evaluator
            # Fallback: use any available model different from generator
            return self._fallback_evaluator(generator_model)

        # For claude-* generators, use deepseek-reasoner
        if generator_model.startswith("claude-"):
            if settings.deepseek_api_key:
                return "deepseek-reasoner"

        return self._fallback_evaluator(generator_model)

    @staticmethod
    def _fallback_evaluator(generator_model: str) -> str:
        """Pick any evaluator different from the generator."""
        candidates = ["deepseek-chat", "deepseek-reasoner"]
        for c in candidates:
            if c != generator_model:
                return c
        return settings.eval_model

    def _compute_metric(
        self,
        dim_key: str,
        artifacts: list[str],
        subtopics: list[str],
        artifacts_by_type: dict[str, list[str]] | None = None,
    ) -> DimensionScore:
        """Dispatch to the right computable metric function."""
        if dim_key == "coverage_breadth":
            return coverage_breadth(artifacts, subtopics)
        if dim_key == "source_diversity":
            return source_diversity(artifacts)
        if dim_key == "terminology_coverage":
            return terminology_coverage(artifacts, subtopics)
        if dim_key == "citation_density":
            return citation_density(artifacts)
        if dim_key == "structural_completeness":
            combined = "\n".join(artifacts)
            return structural_completeness(combined)
        if dim_key == "internal_consistency":
            return internal_consistency_keyword(artifacts)
        if dim_key == "evidence_mapping":
            by_type = artifacts_by_type or {}
            hypotheses = by_type.get("hypotheses", [])
            evidence_texts = by_type.get("evidence_findings", [])
            return evidence_mapping(hypotheses, evidence_texts)
        if dim_key == "specificity":
            return specificity(artifacts)
        # Unknown computable dimension
        return DimensionScore(name=dim_key, computable_value=0.0)

    async def _evaluate_dimension_llm(
        self,
        dim_key: str,
        artifacts: list[str],
        phase: ResearchPhase,
        model: str,
    ) -> DimensionScore:
        """Evaluate a dimension using LLM."""
        combined = "\n---\n".join(a[:2000] for a in artifacts[:5])
        criteria = _DIMENSION_CRITERIA.get(dim_key, "Evaluate quality and completeness.")
        prompt = _LLM_EVAL_PROMPT.format(
            dimension=dim_key,
            phase=phase.value,
            criteria=criteria,
            artifacts=combined[:8000],
        )

        try:
            response = await self._router.generate(model, prompt, json_mode=True)
        except Exception:
            logger.exception("LLM evaluation failed for %s", dim_key)
            return DimensionScore(name=dim_key, llm_value=0.0)

        data = safe_json_loads(response, fallback={})
        if not isinstance(data, dict):
            return DimensionScore(name=dim_key, llm_value=0.0)

        llm_val = float(data.get("score", 0.0))

        # Parse structured evidence items into flat string list for DimensionScore
        raw_evidence = data.get("evidence", [])
        evidence: list[str] = []
        if isinstance(raw_evidence, list):
            for item in raw_evidence:
                if isinstance(item, dict):
                    finding = item.get("finding", "")
                    artifact_ref = item.get("artifact_ref", "")
                    impact = item.get("impact", "neutral")
                    evidence.append(f"[{impact}] {finding} (ref: {artifact_ref})")
                else:
                    evidence.append(str(item))
        else:
            evidence = [str(raw_evidence)]

        # Append missing items as negative evidence
        missing = data.get("missing", [])
        if isinstance(missing, list):
            for m in missing:
                evidence.append(f"[missing] {m}")

        return DimensionScore(
            name=dim_key,
            llm_value=min(max(llm_val, 0.0), 1.0),
            combined=min(max(llm_val, 0.0), 1.0),
            evidence=evidence,
        )

    async def _collect_artifacts(self, board: Blackboard) -> list[str]:
        """Collect all non-superseded artifact texts from the board."""
        texts: list[str] = []
        for art_type in ArtifactType:
            metas = await board.list_artifacts(art_type)
            for m in metas:
                ver = await board.get_latest_version(art_type, m.artifact_id)
                if ver == 0:
                    continue
                content = await board.read_artifact(art_type, m.artifact_id, ver, ContextLevel.L2)
                if not content:
                    continue
                text = content if isinstance(content, str) else json.dumps(content)
                texts.append(text)
        return texts

    async def _collect_artifacts_by_type(self, board: Blackboard) -> dict[str, list[str]]:
        """Collect artifact texts grouped by ArtifactType value."""
        by_type: dict[str, list[str]] = {}
        for art_type in ArtifactType:
            texts: list[str] = []
            metas = await board.list_artifacts(art_type)
            for m in metas:
                ver = await board.get_latest_version(art_type, m.artifact_id)
                if ver == 0:
                    continue
                content = await board.read_artifact(art_type, m.artifact_id, ver, ContextLevel.L2)
                if not content:
                    continue
                text = content if isinstance(content, str) else json.dumps(content)
                texts.append(text)
            if texts:
                by_type[art_type.value] = texts
        return by_type

    async def save_to_db(self, evaluation: PhaseEvaluation, iteration: int) -> None:
        """Public method to persist evaluation to DB."""
        if not self._project_id:
            logger.warning("save_to_db called without project_id, skipping")
            return
        await self._save_evaluation_to_db(evaluation, iteration)

    async def _save_evaluation_to_db(self, evaluation: PhaseEvaluation, iteration: int) -> None:
        """Persist PhaseEvaluation to evaluation_results table."""
        try:
            from backend.evaluation.store import EvaluationStore

            await EvaluationStore.save_evaluation(self._project_id, evaluation, iteration)
            logger.info("Saved evaluation to DB for project %s", self._project_id)
        except Exception:
            logger.exception("Failed to save evaluation to DB (non-fatal)")

    async def _save_claims_to_db(
        self,
        claims: list[Claim],
        contradictions: list[Contradiction],
    ) -> None:
        """Persist claims and contradictions to DB."""
        try:
            from backend.evaluation.store import ClaimStore, ContradictionStore

            claim_ids = await ClaimStore.save_claims(self._project_id, claims)
            # Build mapping: pydantic claim_id → DB UUID
            claim_id_map: dict[str, uuid.UUID] = {}
            for pydantic_claim, db_uuid in zip(claims, claim_ids):
                claim_id_map[pydantic_claim.claim_id] = db_uuid

            if contradictions:
                await ContradictionStore.save_contradictions(
                    self._project_id, contradictions, claim_id_map
                )
            logger.info(
                "Saved %d claims, %d contradictions to DB",
                len(claim_ids),
                len(contradictions),
            )
        except Exception:
            logger.exception("Failed to save claims/contradictions to DB (non-fatal)")

    async def _extract_subtopics(self, board: Blackboard) -> list[str]:
        """Extract subtopics from research topic and directions."""
        meta = await board.get_project_meta()
        topic = meta.get("research_topic", "")
        subtopics = _tokenize_topic(topic) if topic else []

        # Add terms from direction artifacts
        directions = await board.list_artifacts(ArtifactType.DIRECTIONS)
        for m in directions:
            ver = await board.get_latest_version(ArtifactType.DIRECTIONS, m.artifact_id)
            if ver == 0:
                continue
            content = await board.read_artifact(
                ArtifactType.DIRECTIONS, m.artifact_id, ver, ContextLevel.L2
            )
            if isinstance(content, str):
                subtopics.extend(_tokenize_topic(content)[:20])
        return subtopics
