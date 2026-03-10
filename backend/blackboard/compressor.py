"""Dedup compressor -- detect and resolve artifact duplication."""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.types import ArtifactType, ContextLevel, DedupDecision

if TYPE_CHECKING:
    from backend.blackboard.board import Blackboard
    from backend.knowledge.embeddings import EmbeddingService

logger = logging.getLogger(__name__)

LLMCall = Callable[[list[dict[str, str]]], Awaitable[str]]

_MERGE_POLICIES: dict[ArtifactType, str] = {
    ArtifactType.HYPOTHESES: "mergeable",
    ArtifactType.EVIDENCE_FINDINGS: "never",
    ArtifactType.EVIDENCE_GAPS: "never",
    ArtifactType.DIRECTIONS: "mergeable",
    ArtifactType.EXPERIMENT_GUIDE: "never",
    ArtifactType.OUTLINE: "never",
    ArtifactType.DRAFT: "never",
    ArtifactType.REVIEW: "never",
}

_SIMILARITY_THRESHOLD = 0.80


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class DedupCheckResult:
    decision: DedupDecision
    existing_id: str | None = None
    existing_type: ArtifactType | None = None
    reason: str = ""


class DedupCompressor:
    def __init__(self, embedding_service: EmbeddingService) -> None:
        self._embeddings = embedding_service

    async def check_and_deduplicate(
        self,
        board: Blackboard,
        new_artifact_type: ArtifactType,
        new_content: str,
        llm_call: LLMCall,
    ) -> DedupCheckResult:
        candidates = await self._find_similar(board, new_artifact_type, new_content)

        if not candidates:
            return DedupCheckResult(
                decision=DedupDecision.CREATE,
                reason="No similar artifacts found",
            )

        merge_policy = _MERGE_POLICIES.get(new_artifact_type, "never")
        return await self._llm_dedup_decision(
            new_content,
            candidates,
            new_artifact_type,
            merge_policy,
            llm_call,
        )

    # ------------------------------------------------------------------
    # Step 1: Vector pre-filter
    # ------------------------------------------------------------------

    async def _find_similar(
        self,
        board: Blackboard,
        artifact_type: ArtifactType,
        new_content: str,
    ) -> list[tuple[str, float]]:
        metas = await board.list_artifacts(artifact_type)
        if not metas:
            return []

        new_emb = await self._embeddings.embed_text(new_content)

        l0_texts: list[str] = []
        ids: list[str] = []
        for m in metas:
            ver = await board.get_latest_version(artifact_type, m.artifact_id)
            if ver == 0:
                continue
            l0 = await board.read_artifact(
                artifact_type,
                m.artifact_id,
                ver,
                ContextLevel.L0,
            )
            if l0 and isinstance(l0, str):
                l0_texts.append(l0)
                ids.append(m.artifact_id)

        if not l0_texts:
            return []

        l0_embs = await self._embeddings.embed_batch(l0_texts)
        results: list[tuple[str, float]] = []
        for aid, emb in zip(ids, l0_embs):
            sim = _cosine_similarity(new_emb, emb)
            if sim >= _SIMILARITY_THRESHOLD:
                results.append((aid, sim))

        return sorted(results, key=lambda x: x[1], reverse=True)

    # ------------------------------------------------------------------
    # Step 2: LLM dedup decision
    # ------------------------------------------------------------------

    async def _llm_dedup_decision(
        self,
        new_content: str,
        candidates: list[tuple[str, float]],
        artifact_type: ArtifactType,
        merge_policy: str,
        llm_call: LLMCall,
    ) -> DedupCheckResult:
        candidate_desc = "\n".join(f"- ID: {cid}, Similarity: {sim:.3f}" for cid, sim in candidates)
        prompt = (
            f"A new {artifact_type.value} artifact is being created. "
            f"Similar existing artifacts were found:\n{candidate_desc}\n\n"
            f"New content (truncated):\n{new_content[:2000]}\n\n"
            f"Merge policy for {artifact_type.value}: {merge_policy}\n\n"
            "Decide one of: SKIP (exact duplicate), CREATE (sufficiently different), "
            "MERGE (combine with existing), SUPERSEDE (replace existing).\n"
            'Respond with JSON: {"decision": "...", "existing_id": "...", "reason": "..."}'
        )

        try:
            result = await llm_call(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are a deduplication assistant. Respond with valid JSON only."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ]
            )
            data = json.loads(result.strip())
            decision = DedupDecision(data.get("decision", "create").lower())

            if merge_policy == "never" and decision == DedupDecision.MERGE:
                decision = DedupDecision.CREATE

            return DedupCheckResult(
                decision=decision,
                existing_id=data.get("existing_id"),
                existing_type=artifact_type,
                reason=data.get("reason", ""),
            )
        except Exception as exc:
            logger.warning("LLM dedup failed: %s", exc)
            if candidates and candidates[0][1] > 0.95:
                return DedupCheckResult(
                    decision=DedupDecision.SKIP,
                    existing_id=candidates[0][0],
                    existing_type=artifact_type,
                    reason="Very high similarity; LLM unavailable",
                )
            return DedupCheckResult(
                decision=DedupDecision.CREATE,
                reason="LLM unavailable, defaulting to create",
            )
