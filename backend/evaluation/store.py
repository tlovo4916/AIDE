"""DB persistence layer for evaluation results, claims, and contradictions."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import select

from backend.types import Claim as PydanticClaim
from backend.types import Contradiction as PydanticContradiction
from backend.types import InformationGainMetric, PhaseEvaluation

logger = logging.getLogger(__name__)

# Confidence string → float mapping
_CONFIDENCE_MAP: dict[str, float] = {
    "strong": 1.0,
    "moderate": 0.7,
    "tentative": 0.4,
}


class ClaimStore:
    """Persist and load Pydantic Claim objects to/from the claims table."""

    @staticmethod
    async def save_claims(project_id: str, claims: list[PydanticClaim]) -> list[uuid.UUID]:
        """Save claims to DB. Returns list of generated UUIDs."""
        if not claims:
            return []

        from backend.models import async_session_factory
        from backend.models.claim import Claim as ClaimORM

        ids: list[uuid.UUID] = []
        async with async_session_factory() as session:
            async with session.begin():
                for c in claims:
                    row_id = uuid.uuid4()
                    confidence_float = _CONFIDENCE_MAP.get(c.confidence, 0.7)
                    row = ClaimORM(
                        id=row_id,
                        project_id=uuid.UUID(project_id),
                        artifact_id=None,
                        text=c.text,
                        confidence=confidence_float,
                        source_agent=c.source_artifact[:50] if c.source_artifact else None,
                    )
                    session.add(row)
                    ids.append(row_id)
        return ids

    @staticmethod
    async def load_claims(project_id: str) -> list[PydanticClaim]:
        """Load all claims for a project from DB."""
        from backend.models import async_session_factory
        from backend.models.claim import Claim as ClaimORM

        async with async_session_factory() as session:
            stmt = (
                select(ClaimORM)
                .where(ClaimORM.project_id == uuid.UUID(project_id))
                .order_by(ClaimORM.created_at)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

        # Reverse-map confidence float → string
        rev_map = {v: k for k, v in _CONFIDENCE_MAP.items()}

        claims: list[PydanticClaim] = []
        for row in rows:
            conf_str = rev_map.get(row.confidence, "moderate")
            claims.append(
                PydanticClaim(
                    claim_id=str(row.id),
                    text=row.text,
                    source_artifact=row.source_agent or "",
                    confidence=conf_str,
                )
            )
        return claims


class ContradictionStore:
    """Persist and load contradictions to/from the contradictions table."""

    @staticmethod
    async def save_contradictions(
        project_id: str,
        contradictions: list[PydanticContradiction],
        claim_id_map: dict[str, uuid.UUID],
    ) -> list[uuid.UUID]:
        """Save contradictions to DB.

        Args:
            project_id: Project UUID string.
            contradictions: Pydantic Contradiction objects.
            claim_id_map: Mapping from Pydantic claim_id (short) to DB UUID.

        Returns:
            List of generated contradiction UUIDs.
        """
        if not contradictions:
            return []

        from backend.models import async_session_factory
        from backend.models.claim import Contradiction as ContradictionORM

        ids: list[uuid.UUID] = []
        async with async_session_factory() as session:
            async with session.begin():
                for c in contradictions:
                    claim_a_uuid = claim_id_map.get(c.claim_a.claim_id)
                    claim_b_uuid = claim_id_map.get(c.claim_b.claim_id)
                    if not claim_a_uuid or not claim_b_uuid:
                        logger.warning(
                            "Skipping contradiction %s: missing claim UUID mapping",
                            c.contradiction_id,
                        )
                        continue

                    row_id = uuid.uuid4()
                    evidence_json = json.dumps(
                        {
                            "explanation": c.explanation,
                            "relationship": c.relationship,
                            "detected_by": c.detected_by,
                        },
                        ensure_ascii=False,
                    )
                    row = ContradictionORM(
                        id=row_id,
                        project_id=uuid.UUID(project_id),
                        claim_a_id=claim_a_uuid,
                        claim_b_id=claim_b_uuid,
                        confidence=c.severity,
                        evidence=evidence_json,
                        status="detected",
                    )
                    session.add(row)
                    ids.append(row_id)
        return ids

    @staticmethod
    async def load_contradictions(project_id: str) -> list[dict[str, Any]]:
        """Load contradictions for a project. Returns raw dicts (claims not joined)."""
        from backend.models import async_session_factory
        from backend.models.claim import Contradiction as ContradictionORM

        async with async_session_factory() as session:
            stmt = (
                select(ContradictionORM)
                .where(ContradictionORM.project_id == uuid.UUID(project_id))
                .order_by(ContradictionORM.created_at)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

        items: list[dict[str, Any]] = []
        for row in rows:
            evidence_data: dict[str, Any] = {}
            if row.evidence:
                try:
                    evidence_data = json.loads(row.evidence)
                except (json.JSONDecodeError, TypeError):
                    evidence_data = {"raw": row.evidence}

            items.append(
                {
                    "id": str(row.id),
                    "claim_a_id": str(row.claim_a_id),
                    "claim_b_id": str(row.claim_b_id),
                    "confidence": row.confidence,
                    "evidence": evidence_data,
                    "status": row.status,
                }
            )
        return items


class EvaluationStore:
    """Persist evaluation results and iteration metrics to DB."""

    @staticmethod
    async def save_evaluation(
        project_id: str,
        evaluation: PhaseEvaluation,
        iteration: int,
    ) -> uuid.UUID:
        """Save a PhaseEvaluation to the evaluation_results table."""
        from backend.models import async_session_factory
        from backend.models.evaluation import EvaluationResult

        row_id = uuid.uuid4()
        dimensions_json = {k: v.model_dump(mode="json") for k, v in evaluation.dimensions.items()}
        raw_evidence = evaluation.raw_evidence or {}

        async with async_session_factory() as session:
            async with session.begin():
                row = EvaluationResult(
                    id=row_id,
                    project_id=uuid.UUID(project_id),
                    artifact_id=None,
                    evaluator_model=evaluation.evaluator_model,
                    evaluator_provider=evaluation.evaluator_provider or None,
                    phase=evaluation.phase.value,
                    iteration=iteration,
                    dimensions=dimensions_json,
                    composite_score=evaluation.composite_score,
                    raw_evidence=raw_evidence if raw_evidence else None,
                )
                session.add(row)
        return row_id

    @staticmethod
    async def save_iteration_metric(
        project_id: str,
        phase: str,
        iteration: int,
        metric: InformationGainMetric,
        eval_composite: float,
    ) -> uuid.UUID:
        """Save an iteration metric row."""
        from backend.models import async_session_factory
        from backend.models.iteration_metric import IterationMetric

        row_id = uuid.uuid4()
        async with async_session_factory() as session:
            async with session.begin():
                row = IterationMetric(
                    id=row_id,
                    project_id=uuid.UUID(project_id),
                    phase=phase,
                    iteration=iteration,
                    information_gain=metric.information_gain,
                    artifact_count_delta=metric.artifact_count_delta,
                    unique_claim_delta=metric.unique_claim_delta,
                    eval_composite=eval_composite,
                    metrics={
                        "is_diminishing": metric.is_diminishing,
                        "is_loop_detected": metric.is_loop_detected,
                    },
                )
                session.add(row)
        return row_id
