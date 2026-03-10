"""Web retrieval from Semantic Scholar and arXiv APIs."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"
ARXIV_API_BASE = "https://export.arxiv.org/api/query"
REQUEST_DELAY = 1.5
_MAX_RETRIES = 3
_RATE_LIMIT_BACKOFF = 15.0


def _extract_english_keywords(text: str) -> str:
    """Extract ASCII words from text; if none, transliterate key concepts."""
    ascii_words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", text)
    if ascii_words:
        return " ".join(ascii_words[:12])
    _CN_TO_EN: dict[str, str] = {
        "纳米": "nanomaterial", "材料": "material", "免疫": "immune",
        "脓毒症": "sepsis", "炎症": "inflammation", "抗炎": "anti-inflammatory",
        "巨噬细胞": "macrophage", "训练免疫": "trained immunity",
        "细胞因子": "cytokine", "氧化应激": "oxidative stress",
        "靶向": "targeted", "递送": "delivery", "脂质体": "liposome",
        "聚合物": "polymer", "水凝胶": "hydrogel", "肿瘤": "tumor",
        "蛋白": "protein", "基因": "gene", "检索": "retrieval",
        "深度学习": "deep learning", "注意力": "attention",
        "大语言模型": "large language model", "机器学习": "machine learning",
    }
    en_parts: list[str] = []
    remaining = text
    for cn, en in sorted(_CN_TO_EN.items(), key=lambda x: -len(x[0])):
        if cn in remaining:
            en_parts.append(en)
            remaining = remaining.replace(cn, "", 1)
    return " ".join(en_parts[:8]) if en_parts else text[:60]


class WebRetriever:

    def __init__(self) -> None:
        headers: dict[str, str] = {}
        if settings.semantic_scholar_api_key:
            headers["x-api-key"] = settings.semantic_scholar_api_key
        self._s2_client = httpx.AsyncClient(
            base_url=SEMANTIC_SCHOLAR_BASE,
            headers=headers,
            timeout=30.0,
        )
        self._arxiv_client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        await self._s2_client.aclose()
        await self._arxiv_client.aclose()

    async def search_semantic_scholar(
        self, query: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        logger.info("[WebRetriever] S2 query: %r", query[:80])
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = await self._s2_client.get(
                    "/paper/search",
                    params={
                        "query": query,
                        "limit": limit,
                        "fields": "paperId,title,abstract,authors,year,citationCount,externalIds",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                await asyncio.sleep(REQUEST_DELAY)
                results = [_normalize_s2(p) for p in data.get("data", [])]
                logger.info("[WebRetriever] S2 returned %d papers", len(results))
                return results
            except httpx.HTTPStatusError as exc:
                is_rate_limit = exc.response.status_code == 429
                if is_rate_limit:
                    # Respect Retry-After header when available
                    retry_after = exc.response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = max(float(retry_after), _RATE_LIMIT_BACKOFF)
                        except ValueError:
                            delay = _RATE_LIMIT_BACKOFF * (attempt + 1)
                    else:
                        delay = _RATE_LIMIT_BACKOFF * (attempt + 1)
                else:
                    delay = REQUEST_DELAY * (attempt + 1)
                logger.warning(
                    "[WebRetriever] S2 attempt %d/%d failed (%d): backoff %.0fs",
                    attempt + 1, _MAX_RETRIES + 1, exc.response.status_code, delay,
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(delay)
            except Exception as exc:
                logger.warning(
                    "[WebRetriever] S2 attempt %d/%d failed: %s",
                    attempt + 1, _MAX_RETRIES + 1, exc,
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(REQUEST_DELAY * (attempt + 1))
        return []

    async def search_arxiv(
        self, query: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        en_query = _extract_english_keywords(query)
        logger.info("[WebRetriever] arXiv query: %r (original: %r)", en_query, query[:60])
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = await self._arxiv_client.get(
                    ARXIV_API_BASE,
                    params={
                        "search_query": f"all:{en_query}",
                        "start": 0,
                        "max_results": limit,
                    },
                )
                resp.raise_for_status()
                await asyncio.sleep(REQUEST_DELAY)
                results = _parse_arxiv_atom(resp.text)
                logger.info("[WebRetriever] arXiv returned %d papers", len(results))
                return results
            except Exception as exc:
                logger.warning(
                    "[WebRetriever] arXiv attempt %d/%d failed: %s",
                    attempt + 1, _MAX_RETRIES + 1, exc,
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(REQUEST_DELAY * (attempt + 1))
        return []


def _normalize_s2(paper: dict[str, Any]) -> dict[str, Any]:
    authors = [
        a.get("name", "") for a in paper.get("authors", [])
    ]
    ext = paper.get("externalIds", {}) or {}
    return {
        "paper_id": paper.get("paperId", ""),
        "title": paper.get("title", ""),
        "abstract": paper.get("abstract", ""),
        "authors": authors,
        "year": paper.get("year"),
        "citation_count": paper.get("citationCount", 0),
        "doi": ext.get("DOI", ""),
        "arxiv_id": ext.get("ArXiv", ""),
        "source": "semantic_scholar",
    }


def _parse_arxiv_atom(xml_text: str) -> list[dict[str, Any]]:
    import xml.etree.ElementTree as ET

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_text)
    results: list[dict[str, Any]] = []

    for entry in root.findall("atom:entry", ns):
        title_el = entry.find("atom:title", ns)
        summary_el = entry.find("atom:summary", ns)
        published_el = entry.find("atom:published", ns)
        arxiv_id_el = entry.find("atom:id", ns)

        authors = [
            name_el.text or ""
            for a in entry.findall("atom:author", ns)
            if (name_el := a.find("atom:name", ns)) is not None
        ]

        year = None
        if published_el is not None and published_el.text:
            year = int(published_el.text[:4])

        aid = ""
        if arxiv_id_el is not None and arxiv_id_el.text:
            aid = arxiv_id_el.text.split("/abs/")[-1]

        results.append({
            "paper_id": aid,
            "title": (title_el.text or "").strip() if title_el is not None else "",
            "abstract": (summary_el.text or "").strip() if summary_el is not None else "",
            "authors": authors,
            "year": year,
            "citation_count": 0,
            "doi": "",
            "arxiv_id": aid,
            "source": "arxiv",
        })

    return results
