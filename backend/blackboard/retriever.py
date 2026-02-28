"""Directory-recursive retriever for blackboard artifacts."""

from __future__ import annotations

import math
from typing import Any, TYPE_CHECKING

from backend.types import ArtifactMeta, ArtifactType, ContextLevel

if TYPE_CHECKING:
    from backend.blackboard.board import Blackboard
    from backend.knowledge.embeddings import EmbeddingService

_TYPE_KEYWORDS: dict[ArtifactType, set[str]] = {
    ArtifactType.DIRECTIONS: {
        "direction", "research", "scope", "goal", "topic", "field",
    },
    ArtifactType.HYPOTHESES: {
        "hypothesis", "hypotheses", "claim", "theory", "prediction",
    },
    ArtifactType.EVIDENCE_FINDINGS: {
        "evidence", "finding", "result", "data", "study", "paper",
    },
    ArtifactType.EVIDENCE_GAPS: {
        "gap", "missing", "unknown", "need", "lack",
    },
    ArtifactType.EXPERIMENT_GUIDE: {
        "experiment", "methodology", "protocol", "design",
    },
    ArtifactType.OUTLINE: {
        "outline", "structure", "section", "organization",
    },
    ArtifactType.DRAFT: {
        "draft", "writing", "manuscript", "paper", "document",
    },
    ArtifactType.REVIEW: {
        "review", "critique", "feedback", "assessment", "evaluation",
    },
}


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class DirectoryRecursiveRetriever:

    def __init__(self, embedding_service: EmbeddingService) -> None:
        self._embeddings = embedding_service

    async def retrieve(
        self,
        board: Blackboard,
        query: str,
        top_k: int = 5,
        level: ContextLevel = ContextLevel.L1,
    ) -> list[dict[str, Any]]:
        query_emb = await self._embeddings.embed_text(query)

        target_types = self._analyze_intent(query)

        dir_data = await self._collect_directory_data(board, target_types)
        if not dir_data:
            return []

        dir_scores = self._score_directories(query_emb, dir_data)

        candidates = self._drill_down(query_emb, dir_data, dir_scores, top_k)

        return await self._fetch_at_level(board, candidates[:top_k], level)

    # ------------------------------------------------------------------
    # Step 1: Intent analysis
    # ------------------------------------------------------------------

    @staticmethod
    def _analyze_intent(query: str) -> list[ArtifactType]:
        query_lower = query.lower()
        scored: list[tuple[int, ArtifactType]] = []
        for at, keywords in _TYPE_KEYWORDS.items():
            matches = sum(1 for k in keywords if k in query_lower)
            if matches > 0:
                scored.append((matches, at))
        if not scored:
            return list(ArtifactType)
        scored.sort(key=lambda x: x[0], reverse=True)
        return [at for _, at in scored]

    # ------------------------------------------------------------------
    # Step 2: Collect L0 data and embeddings per directory
    # ------------------------------------------------------------------

    async def _collect_directory_data(
        self,
        board: Blackboard,
        target_types: list[ArtifactType],
    ) -> dict[ArtifactType, list[tuple[ArtifactMeta, int, list[float]]]]:
        dir_data: dict[
            ArtifactType, list[tuple[ArtifactMeta, int, list[float]]]
        ] = {}

        for at in target_types:
            metas = await board.list_artifacts(at)
            if not metas:
                continue
            l0_texts: list[str] = []
            meta_versions: list[tuple[ArtifactMeta, int]] = []
            for m in metas:
                ver = await board.get_latest_version(at, m.artifact_id)
                if ver == 0:
                    continue
                l0 = await board.read_artifact(at, m.artifact_id, ver, ContextLevel.L0)
                if l0 and isinstance(l0, str):
                    l0_texts.append(l0)
                    meta_versions.append((m, ver))
            if not l0_texts:
                continue
            l0_embs = await self._embeddings.embed_batch(l0_texts)
            dir_data[at] = [
                (m, ver, emb)
                for (m, ver), emb in zip(meta_versions, l0_embs)
            ]

        return dir_data

    # ------------------------------------------------------------------
    # Step 2b: Directory scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _score_directories(
        query_emb: list[float],
        dir_data: dict[ArtifactType, list[tuple[ArtifactMeta, int, list[float]]]],
    ) -> dict[ArtifactType, float]:
        scores: dict[ArtifactType, float] = {}
        for at, items in dir_data.items():
            sims = [_cosine_similarity(query_emb, emb) for _, _, emb in items]
            scores[at] = sum(sims) / len(sims)
        return scores

    # ------------------------------------------------------------------
    # Step 3: Recursive drill-down with score propagation
    # ------------------------------------------------------------------

    @staticmethod
    def _drill_down(
        query_emb: list[float],
        dir_data: dict[ArtifactType, list[tuple[ArtifactMeta, int, list[float]]]],
        dir_scores: dict[ArtifactType, float],
        top_k: int,
    ) -> list[tuple[float, ArtifactType, str, int]]:
        candidates: list[tuple[float, ArtifactType, str, int]] = []
        prev_top_k: set[tuple[str, str]] = set()
        stable_rounds = 0

        for at, _dir_score in sorted(
            dir_scores.items(), key=lambda x: x[1], reverse=True
        ):
            for meta, ver, emb in dir_data[at]:
                own_score = _cosine_similarity(query_emb, emb)
                propagated = 0.5 * own_score + 0.5 * _dir_score
                candidates.append((propagated, at, meta.artifact_id, ver))

            candidates.sort(key=lambda x: x[0], reverse=True)
            current_top = {
                (c[1].value, c[2]) for c in candidates[:top_k]
            }
            if current_top == prev_top_k:
                stable_rounds += 1
                if stable_rounds >= 2:
                    break
            else:
                stable_rounds = 0
            prev_top_k = current_top

        return candidates

    # ------------------------------------------------------------------
    # Step 5: Fetch results at requested level
    # ------------------------------------------------------------------

    @staticmethod
    async def _fetch_at_level(
        board: Blackboard,
        candidates: list[tuple[float, ArtifactType, str, int]],
        level: ContextLevel,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for score, at, aid, ver in candidates:
            content = await board.read_artifact(at, aid, ver, level)
            meta = await board.read_artifact_meta(at, aid)
            results.append({
                "artifact_type": at.value,
                "artifact_id": aid,
                "version": ver,
                "score": score,
                "content": content,
                "meta": meta.model_dump(mode="json") if meta else {},
            })
        return results
