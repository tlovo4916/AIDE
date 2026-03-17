"""Per-phase dimension definitions for multi-dimensional evaluation."""

from __future__ import annotations

from backend.types import EvaluationDimension, ResearchPhase

# Each entry: (dimension, eval_type, weight)
# eval_type: "computable" = pure algorithmic, "llm" = LLM-graded, "mixed" = both
PHASE_DIMENSIONS: dict[ResearchPhase, list[tuple[EvaluationDimension | str, str, float]]] = {
    ResearchPhase.EXPLORE: [
        (EvaluationDimension.COVERAGE_BREADTH, "computable", 0.3),
        (EvaluationDimension.SOURCE_DIVERSITY, "computable", 0.2),
        (EvaluationDimension.TERMINOLOGY_COVERAGE, "computable", 0.2),
        ("gap_identification", "llm", 0.3),
    ],
    ResearchPhase.HYPOTHESIZE: [
        (EvaluationDimension.SPECIFICITY, "mixed", 0.3),
        (EvaluationDimension.NOVELTY, "llm", 0.3),
        (EvaluationDimension.LOGICAL_COHERENCE, "llm", 0.2),
        (EvaluationDimension.COVERAGE_BREADTH, "computable", 0.2),
    ],
    ResearchPhase.EVIDENCE: [
        (EvaluationDimension.CITATION_DENSITY, "computable", 0.25),
        (EvaluationDimension.EVIDENCE_MAPPING, "mixed", 0.25),
        (EvaluationDimension.METHODOLOGICAL_RIGOR, "llm", 0.25),
        (EvaluationDimension.SOURCE_DIVERSITY, "computable", 0.25),
    ],
    ResearchPhase.COMPOSE: [
        (EvaluationDimension.STRUCTURAL_COMPLETENESS, "computable", 0.25),
        (EvaluationDimension.ARGUMENT_FLOW, "llm", 0.25),
        (EvaluationDimension.CITATION_INTEGRATION, "mixed", 0.25),
        (EvaluationDimension.INTERNAL_CONSISTENCY, "computable", 0.25),
    ],
    ResearchPhase.SYNTHESIZE: [
        (EvaluationDimension.COVERAGE_BREADTH, "computable", 0.2),
        (EvaluationDimension.INTERNAL_CONSISTENCY, "computable", 0.2),
        (EvaluationDimension.ARGUMENT_FLOW, "llm", 0.3),
        (EvaluationDimension.NOVELTY, "llm", 0.3),
    ],
}


def get_dimensions(
    phase: ResearchPhase,
) -> list[tuple[EvaluationDimension | str, str, float]]:
    """Return dimension definitions for a research phase.

    Falls back to EXPLORE dimensions if the phase is not mapped.
    """
    return PHASE_DIMENSIONS.get(phase, PHASE_DIMENSIONS[ResearchPhase.EXPLORE])
