"""Hybrid search: vector + BM25 with RRF, time decay, and MMR reranking."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

import numpy as np

from backend.config import settings
from backend.knowledge.bm25_store import BM25Store
from backend.knowledge.embeddings import EmbeddingService
from backend.knowledge.vector_store import VectorStore
from backend.types import SearchResult

RRF_K = 60


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a)
    vb = np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


class HybridSearchEngine:
    def __init__(
        self,
        vector_store: VectorStore,
        bm25_store: BM25Store,
        embedding_service: EmbeddingService,
    ) -> None:
        self._vector = vector_store
        self._bm25 = bm25_store
        self._embed = embedding_service

    async def search(
        self,
        queries: list[str],
        top_k: int | None = None,
        mmr_lambda: float | None = None,
        time_decay_factor: float | None = None,
    ) -> list[SearchResult]:
        top_k = top_k or settings.hybrid_search_top_k
        mmr_lambda = mmr_lambda if mmr_lambda is not None else settings.mmr_lambda
        time_decay_factor = (
            time_decay_factor if time_decay_factor is not None else settings.time_decay_factor
        )

        query_embeddings = await self._embed.embed_batch(queries)

        vector_results = self._vector.query(
            query_embeddings=query_embeddings,
            n_results=top_k * 2,
        )
        bm25_results_per_query = [self._bm25.query(q, n_results=top_k * 2) for q in queries]

        rrf_scores: dict[str, float] = {}
        doc_data: dict[str, dict[str, Any]] = {}

        if vector_results.get("ids"):
            for qi, ids in enumerate(vector_results["ids"]):
                docs = vector_results.get("documents", [[]])[qi]
                metas = vector_results.get("metadatas", [[]])[qi]
                distances = vector_results.get("distances", [[]])[qi]
                for rank, (did, doc, meta, dist) in enumerate(zip(ids, docs, metas, distances)):
                    rrf_scores[did] = rrf_scores.get(did, 0.0) + 1.0 / (RRF_K + rank + 1)
                    if did not in doc_data:
                        doc_data[did] = {
                            "content": doc or "",
                            "metadata": meta or {},
                            "distance": dist,
                        }

        for bm25_list in bm25_results_per_query:
            for rank, (did, _score) in enumerate(bm25_list):
                rrf_scores[did] = rrf_scores.get(did, 0.0) + 1.0 / (RRF_K + rank + 1)
                if did not in doc_data:
                    doc_data[did] = {
                        "content": "",
                        "metadata": {},
                        "distance": 1.0,
                    }

        now = datetime.utcnow()
        for did in rrf_scores:
            meta = doc_data[did].get("metadata", {})
            pub = meta.get("publish_date")
            if pub:
                try:
                    pub_dt = datetime.fromisoformat(pub)
                    age_years = (now - pub_dt).days / 365.25
                    rrf_scores[did] *= time_decay_factor ** max(age_years, 0)
                except (ValueError, TypeError):
                    pass

        candidates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        selected = self._mmr_rerank(
            candidates=candidates,
            doc_data=doc_data,
            query_embeddings=query_embeddings,
            top_k=top_k,
            lam=mmr_lambda,
        )

        results: list[SearchResult] = []
        for did, score in selected:
            dd = doc_data.get(did, {})
            meta = dd.get("metadata", {})
            pub_date = None
            if meta.get("publish_date"):
                try:
                    pub_date = datetime.fromisoformat(meta["publish_date"])
                except (ValueError, TypeError):
                    pass
            results.append(
                SearchResult(
                    chunk_id=did,
                    content=dd.get("content", ""),
                    source=meta.get("source_file", ""),
                    score=score,
                    metadata=meta,
                    publish_date=pub_date,
                )
            )
        return results

    def _mmr_rerank(
        self,
        candidates: list[tuple[str, float]],
        doc_data: dict[str, dict[str, Any]],
        query_embeddings: list[list[float]],
        top_k: int,
        lam: float,
    ) -> list[tuple[str, float]]:
        if not candidates:
            return []

        np.mean(query_embeddings, axis=0).tolist()

        candidate_embeddings: dict[str, list[float]] = {}
        for did, _ in candidates:
            meta = doc_data.get(did, {}).get("metadata", {})
            emb = meta.get("embedding")
            if emb and isinstance(emb, list):
                candidate_embeddings[did] = emb

        selected: list[tuple[str, float]] = []
        remaining = list(candidates)

        while remaining and len(selected) < top_k:
            best_did = None
            best_score = -math.inf

            for did, rrf_score in remaining:
                relevance = rrf_score

                max_sim = 0.0
                if did in candidate_embeddings:
                    emb = candidate_embeddings[did]
                    for s_did, _ in selected:
                        if s_did in candidate_embeddings:
                            sim = _cosine_similarity(emb, candidate_embeddings[s_did])
                            max_sim = max(max_sim, sim)

                mmr_score = lam * relevance - (1 - lam) * max_sim
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_did = did

            if best_did is None:
                break

            selected.append((best_did, rrf_scores_lookup(remaining, best_did)))
            remaining = [(d, s) for d, s in remaining if d != best_did]

        return selected


def rrf_scores_lookup(candidates: list[tuple[str, float]], did: str) -> float:
    for d, s in candidates:
        if d == did:
            return s
    return 0.0
