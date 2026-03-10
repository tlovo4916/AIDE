"""Librarian agent -- literature search, evidence collection, knowledge base."""

from __future__ import annotations

import logging
import re

from backend.agents.base import BaseAgent
from backend.config import settings
from backend.types import AgentResponse, AgentRole, AgentTask, ArtifactType

logger = logging.getLogger(__name__)

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


class LibrarianAgent(BaseAgent):

    role = AgentRole.LIBRARIAN
    system_prompt_template = "librarian.j2"
    preferred_model = "deepseek-reasoner"
    primary_artifact_types = [ArtifactType.EVIDENCE_FINDINGS]
    dependency_artifact_types = [
        ArtifactType.HYPOTHESES,
        ArtifactType.DIRECTIONS,
    ]
    challengeable_roles = [AgentRole.SCIENTIST]
    can_spawn_subagents = True

    # Cache already-queried search terms to avoid duplicate API calls
    _query_cache: set[str] = set()

    async def execute(self, context: str, task: AgentTask) -> AgentResponse:
        enriched = await self._enrich_context_with_literature(context, task)
        return await super().execute(enriched, task)

    async def _enrich_context_with_literature(
        self, context: str, task: AgentTask
    ) -> str:
        if not settings.enable_web_retrieval:
            logger.info("[Librarian] Web retrieval disabled, skipping")
            return context

        query = (self._research_topic or task.description)[:200].strip()
        if not query:
            return context

        from backend.knowledge.web_retriever import WebRetriever

        has_cjk = bool(_CJK_RE.search(query))
        en_query = await self._translate_query(query) if has_cjk else query

        retriever = WebRetriever()
        papers: list[dict] = []
        try:
            papers = await self._search_with_fallback(retriever, query, en_query)
        except Exception as exc:
            logger.error("[Librarian] All retrieval attempts failed: %s", exc)
        finally:
            await retriever.close()

        if not papers:
            logger.warning("[Librarian] No papers found for query: %s", query[:80])

        # --- Local knowledge base search ---
        local_results = await self._search_local_knowledge(en_query or query)
        if local_results:
            local_lines = ["\n## 本地知识库\n"]
            for r in local_results[:5]:
                source = r.get("source", "unknown")
                content = (r.get("content") or "")[:300].replace("\n", " ")
                score = r.get("score", 0.0)
                local_lines.append(f"- [{source}] (score={score:.2f}) {content}")
            context = context + "\n" + "\n".join(local_lines)
            logger.info("[Librarian] Injected %d local chunks into context", len(local_results[:5]))

        if not papers:
            return context

        lines = ["\n## Real Literature (arXiv / Semantic Scholar)\n"]
        for p in papers:
            authors = p.get("authors", [])
            author_str = ", ".join(authors[:3])
            if len(authors) > 3:
                author_str += " et al."
            abstract = (p.get("abstract") or "")[:300].replace("\n", " ")
            arxiv_id = p.get("arxiv_id", "")
            doi = p.get("doi", "")
            ref = f"arXiv:{arxiv_id}" if arxiv_id else (f"DOI:{doi}" if doi else "")
            lines.append(
                f"- [{p.get('year', '?')}] **{p.get('title', 'Unknown')}** "
                f"({author_str}) {ref}\n  {abstract}"
            )

        logger.info(
            "[Librarian] Injected %d real papers into context (query=%s)",
            len(papers), en_query[:60],
        )
        return context + "\n" + "\n".join(lines)

    async def _search_local_knowledge(self, query: str) -> list[dict]:
        """Search the project's local knowledge base (uploaded PDFs).

        Falls back to BM25-only search when the embedding service is
        unavailable (e.g. SSL certificate errors in Docker).
        """
        if not self._project_id:
            return []
        try:
            from backend.config import settings as _cfg
            from backend.knowledge.bm25_store import BM25Store

            pid = self._project_id
            bm25_path = str(_cfg.project_path(pid) / "bm25_index.json")

            bm25_store = BM25Store(persist_path=bm25_path)
            bm25_store.load()

            # Try hybrid search (vector + BM25) first; fall back to BM25-only
            # if embedding service fails (common cause: SSL errors in Docker).
            try:
                from backend.knowledge.embeddings import EmbeddingService
                from backend.knowledge.hybrid_search import HybridSearchEngine
                from backend.knowledge.vector_store import VectorStore

                collection_name = f"aide_{pid.replace('-', '_')}"
                vector_store = VectorStore(collection_name=collection_name)
                embedding_service = EmbeddingService()
                try:
                    engine = HybridSearchEngine(vector_store, bm25_store, embedding_service)
                    results = await engine.search([query], top_k=5)
                    return [
                        {
                            "chunk_id": r.chunk_id,
                            "content": r.content,
                            "source": r.source,
                            "score": r.score,
                            "metadata": r.metadata,
                        }
                        for r in results
                    ]
                finally:
                    await embedding_service.close()
            except Exception as embed_exc:
                logger.warning(
                    "[Librarian] Hybrid search failed (SSL?), falling back to BM25-only: %s",
                    embed_exc,
                )
                # BM25-only fallback — no embedding needed
                # query() returns list[tuple[doc_id, score]]
                bm25_hits = bm25_store.query(query, n_results=5)
                return [
                    {
                        "chunk_id": doc_id,
                        "content": "",
                        "source": "bm25",
                        "score": score,
                        "metadata": {},
                    }
                    for doc_id, score in bm25_hits
                ]
        except Exception as exc:
            logger.warning("[Librarian] Local knowledge search failed: %s", exc)
            return []

    async def _search_with_fallback(
        self,
        retriever: "WebRetriever",
        original_query: str,
        en_query: str,
    ) -> list[dict]:
        # Deduplicate: skip if we've already searched this query this session
        cache_key = en_query.lower().strip()
        if cache_key in self._query_cache:
            logger.info("[Librarian] Skipping duplicate query: %s", en_query[:60])
            return []
        self._query_cache.add(cache_key)

        # 1) Semantic Scholar with original query (best multilingual support)
        try:
            papers = await retriever.search_semantic_scholar(original_query, limit=5)
            if papers:
                logger.info("[Librarian] Semantic Scholar returned %d papers", len(papers))
                return papers
        except Exception as exc:
            logger.warning("[Librarian] Semantic Scholar search failed: %s", exc)

        # 2) arXiv with English query
        try:
            papers = await retriever.search_arxiv(en_query, limit=5)
            if papers:
                logger.info("[Librarian] arXiv returned %d papers", len(papers))
                return papers
        except Exception as exc:
            logger.warning("[Librarian] arXiv search failed: %s", exc)

        # 3) Semantic Scholar with English query (final fallback)
        if en_query != original_query:
            try:
                papers = await retriever.search_semantic_scholar(en_query, limit=5)
                if papers:
                    logger.info(
                        "[Librarian] Semantic Scholar (EN fallback) returned %d papers",
                        len(papers),
                    )
                    return papers
            except Exception as exc:
                logger.warning("[Librarian] Semantic Scholar EN fallback failed: %s", exc)

        return []

    async def _translate_query(self, query: str) -> str:
        """Use LLM to translate a CJK research query into English keywords for
        academic search APIs.  Falls back to the original query on error."""
        prompt = (
            "Translate the following research topic into an English academic search "
            "query (return ONLY the English keywords, no explanation):\n\n"
            f"{query}"
        )
        try:
            result = await self._llm_router.generate(
                "deepseek-chat", prompt, system_prompt="You are a translator."
            )
            en = result.strip().strip('"').strip("'")
            if en and len(en) > 5:
                logger.info("[Librarian] Translated query: %s -> %s", query[:40], en[:80])
                return en[:200]
        except Exception as exc:
            logger.warning("[Librarian] Query translation failed: %s", exc)
        return query
