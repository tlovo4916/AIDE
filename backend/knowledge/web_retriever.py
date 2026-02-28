"""Web retrieval from Semantic Scholar and arXiv APIs."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from backend.config import settings

SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"
ARXIV_API_BASE = "https://export.arxiv.org/api/query"
REQUEST_DELAY = 1.0


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

        results: list[dict[str, Any]] = []
        for paper in data.get("data", []):
            results.append(_normalize_s2(paper))
        return results

    async def search_arxiv(
        self, query: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        resp = await self._arxiv_client.get(
            ARXIV_API_BASE,
            params={
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": limit,
            },
        )
        resp.raise_for_status()
        await asyncio.sleep(REQUEST_DELAY)
        return _parse_arxiv_atom(resp.text)


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
