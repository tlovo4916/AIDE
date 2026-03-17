"""Relation extractor -- uses LLM to discover semantic relations between artifacts."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from backend.config import settings
from backend.models.artifact import ArtifactRelation
from backend.utils.json_utils import safe_json_loads

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from backend.protocols import LLMRouter

logger = logging.getLogger(__name__)

_VALID_RELATION_TYPES = frozenset(
    {"supports", "contradicts", "refines", "supersedes", "cites", "depends_on"}
)

_SYSTEM_PROMPT = (
    "You are a research relation extractor. Given a NEW artifact and a list of EXISTING "
    "artifacts (each with an ID and summary), identify semantic relations between the new "
    "artifact and the existing ones.\n\n"
    "Output a JSON array of relation objects. Each object has:\n"
    '  - "source": the new artifact ID (UUID string)\n'
    '  - "target": an existing artifact ID (UUID string)\n'
    '  - "relation_type": one of supports, contradicts, refines, supersedes, cites, depends_on\n'
    '  - "confidence": float 0.0-1.0\n'
    '  - "evidence": short explanation\n\n'
    "If no relations exist, output an empty array: []\n"
    "Output raw JSON only, no markdown fences."
)


class RelationExtractor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        llm_router: LLMRouter,
        model: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._llm_router = llm_router
        self._model = model or settings.relation_extraction_model

    async def extract_relations(
        self,
        project_id: str,
        new_artifact_db_id: uuid.UUID,
        new_l1_summary: str,
        recent_artifacts: list[tuple[uuid.UUID, str]],
    ) -> list[ArtifactRelation]:
        """Extract relations between a new artifact and recent artifacts.

        Args:
            project_id: Project UUID string (unused but kept for logging).
            new_artifact_db_id: DB UUID of the new artifact.
            new_l1_summary: L1 summary text of the new artifact.
            recent_artifacts: List of (db_id, l1_summary) for recent artifacts.

        Returns:
            List of ArtifactRelation ORM objects (already persisted to DB).
        """
        if not recent_artifacts:
            return []

        existing_lines = []
        for db_id, summary in recent_artifacts[:15]:
            existing_lines.append(f"- ID: {db_id}\n  Summary: {summary[:300]}")
        existing_block = "\n".join(existing_lines)

        prompt = (
            f"NEW artifact (ID: {new_artifact_db_id}):\n{new_l1_summary[:500]}\n\n"
            f"EXISTING artifacts:\n{existing_block}\n\n"
            "Identify relations from the NEW artifact to any EXISTING artifacts."
        )

        try:
            raw = await self._llm_router.generate(
                self._model,
                prompt,
                system_prompt=_SYSTEM_PROMPT,
                json_mode=True,
            )
        except Exception:
            logger.warning("[RelationExtractor] LLM call failed", exc_info=True)
            return []

        data = safe_json_loads(raw)
        if data is None:
            logger.warning("[RelationExtractor] LLM returned non-JSON: %s", raw[:200])
            return []

        # Accept both list and dict with a "relations" key
        if isinstance(data, dict):
            data = data.get("relations", [])
        if not isinstance(data, list):
            return []

        # Build valid UUID set for target validation
        valid_targets = {str(db_id) for db_id, _ in recent_artifacts}

        relations: list[ArtifactRelation] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            rel_type = item.get("relation_type", "")
            if rel_type not in _VALID_RELATION_TYPES:
                continue
            target_str = str(item.get("target", ""))
            if target_str not in valid_targets:
                continue
            confidence = item.get("confidence", 1.0)
            if not isinstance(confidence, (int, float)):
                confidence = 1.0
            confidence = max(0.0, min(1.0, float(confidence)))

            try:
                target_uuid = uuid.UUID(target_str)
            except ValueError:
                continue

            relations.append(
                ArtifactRelation(
                    source_id=new_artifact_db_id,
                    target_id=target_uuid,
                    relation_type=rel_type,
                    confidence=confidence,
                    evidence=str(item.get("evidence", ""))[:500],
                )
            )

        if relations:
            try:
                async with self._session_factory() as session:
                    session.add_all(relations)
                    await session.commit()
                logger.info(
                    "[RelationExtractor] Persisted %d relations for artifact %s",
                    len(relations),
                    new_artifact_db_id,
                )
            except Exception:
                logger.warning("[RelationExtractor] DB persist failed", exc_info=True)
                return []

        return relations
