"""PDF processing: text extraction, chunking, metadata, and multi-level summaries."""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import tiktoken

from backend.config import settings


class ProcessedChunk:
    __slots__ = (
        "chunk_id",
        "source",
        "content",
        "l0_summary",
        "l1_summary",
        "metadata",
        "token_count",
        "index",
    )

    def __init__(
        self,
        chunk_id: str,
        source: str,
        content: str,
        l0_summary: str,
        l1_summary: str,
        metadata: dict[str, Any],
        token_count: int,
        index: int,
    ) -> None:
        self.chunk_id = chunk_id
        self.source = source
        self.content = content
        self.l0_summary = l0_summary
        self.l1_summary = l1_summary
        self.metadata = metadata
        self.token_count = token_count
        self.index = index

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "source": self.source,
            "content": self.content,
            "l0_summary": self.l0_summary,
            "l1_summary": self.l1_summary,
            "metadata": self.metadata,
            "token_count": self.token_count,
            "index": self.index,
        }


SummarizerFn = Callable[[str, str], Awaitable[str]]


class PDFProcessor:
    def __init__(
        self,
        summarizer: SummarizerFn | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        self._summarizer = summarizer
        self._chunk_size = chunk_size or settings.chunk_size
        self._chunk_overlap = chunk_overlap or settings.chunk_overlap
        self._encoder = tiktoken.encoding_for_model("text-embedding-3-small")

    def _count_tokens(self, text: str) -> int:
        return len(self._encoder.encode(text))

    # -- Text extraction ---------------------------------------------------

    @staticmethod
    def _extract_with_pymupdf(path: Path) -> str:
        import fitz  # type: ignore[import-untyped]

        doc = fitz.open(str(path))
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n\n".join(pages)

    @staticmethod
    def _extract_with_pdfplumber(path: Path) -> str:
        import pdfplumber  # type: ignore[import-untyped]

        with pdfplumber.open(str(path)) as pdf:
            return "\n\n".join(page.extract_text() or "" for page in pdf.pages)

    def extract_text(self, path: Path) -> str:
        try:
            text = self._extract_with_pymupdf(path)
            if text.strip():
                return text
        except Exception:
            pass
        return self._extract_with_pdfplumber(path)

    # -- Metadata heuristics -----------------------------------------------

    @staticmethod
    def extract_metadata(text: str, path: Path) -> dict[str, Any]:
        first_page = text[:3000]
        lines = [line.strip() for line in first_page.split("\n") if line.strip()]

        title = lines[0] if lines else path.stem
        authors = ""
        year = ""
        abstract = ""

        year_match = re.search(r"((?:19|20)\d{2})", first_page)
        if year_match:
            year = year_match.group(1)

        for i, line in enumerate(lines):
            low = line.lower()
            if low.startswith("abstract"):
                abstract_lines = []
                for al in lines[i : i + 10]:
                    if al.lower().startswith("abstract"):
                        al = re.sub(r"(?i)^abstract[:\s]*", "", al)
                    if al.lower().startswith(("introduction", "1.", "keywords")):
                        break
                    abstract_lines.append(al)
                abstract = " ".join(abstract_lines).strip()
                break

        if len(lines) > 1:
            candidate = lines[1]
            if len(candidate) < 300 and not candidate.lower().startswith("abstract"):
                authors = candidate

        return {
            "title": title,
            "authors": authors,
            "year": year,
            "abstract": abstract,
            "source_file": path.name,
        }

    # -- Chunking ----------------------------------------------------------

    def _split_paragraphs(self, text: str) -> list[str]:
        paragraphs = re.split(r"\n{2,}", text)
        return [p.strip() for p in paragraphs if p.strip()]

    def chunk_text(self, text: str) -> list[str]:
        paragraphs = self._split_paragraphs(text)
        chunks: list[str] = []
        current: list[str] = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = self._count_tokens(para)

            if para_tokens > self._chunk_size:
                if current:
                    chunks.append("\n\n".join(current))
                    current, current_tokens = [], 0
                words = para.split()
                buf: list[str] = []
                buf_tokens = 0
                for w in words:
                    wt = self._count_tokens(w + " ")
                    if buf_tokens + wt > self._chunk_size and buf:
                        chunks.append(" ".join(buf))
                        overlap_words = buf[-(self._chunk_overlap // max(wt, 1)) :]
                        buf = list(overlap_words)
                        buf_tokens = self._count_tokens(" ".join(buf))
                    buf.append(w)
                    buf_tokens += wt
                if buf:
                    chunks.append(" ".join(buf))
                continue

            if current_tokens + para_tokens > self._chunk_size and current:
                chunks.append("\n\n".join(current))
                overlap_text = "\n\n".join(current)
                overlap_tokens = self._encoder.encode(overlap_text)
                if len(overlap_tokens) > self._chunk_overlap:
                    overlap_tokens = overlap_tokens[-self._chunk_overlap :]
                    overlap_decoded = self._encoder.decode(overlap_tokens)
                    current = [overlap_decoded]
                    current_tokens = self._chunk_overlap
                else:
                    current = list(current)
                    current_tokens = len(overlap_tokens)
            current.append(para)
            current_tokens += para_tokens

        if current:
            chunks.append("\n\n".join(current))

        return chunks

    # -- Summarization helpers ---------------------------------------------

    async def _generate_l0(self, text: str) -> str:
        if not self._summarizer:
            return text[:200]
        return await self._summarizer(
            "one-line",
            f"Provide a single concise sentence summarizing:\n\n{text[:2000]}",
        )

    async def _generate_l1(self, text: str) -> str:
        if not self._summarizer:
            return text[:600]
        return await self._summarizer(
            "structured",
            (
                "Provide a structured overview (key findings, methods, conclusions) "
                f"of the following text:\n\n{text[:4000]}"
            ),
        )

    # -- Main pipeline -----------------------------------------------------

    async def process(self, path: Path) -> list[ProcessedChunk]:
        text = self.extract_text(path)
        metadata = self.extract_metadata(text, path)
        chunks = self.chunk_text(text)
        source_id = path.stem

        results: list[ProcessedChunk] = []
        for idx, chunk in enumerate(chunks):
            l0 = await self._generate_l0(chunk)
            l1 = await self._generate_l1(chunk)
            results.append(
                ProcessedChunk(
                    chunk_id=f"{source_id}_{idx}_{uuid.uuid4().hex[:8]}",
                    source=source_id,
                    content=chunk,
                    l0_summary=l0,
                    l1_summary=l1,
                    metadata={
                        **metadata,
                        "chunk_index": idx,
                        "total_chunks": len(chunks),
                        "publish_date": datetime.now(UTC).isoformat(),
                    },
                    token_count=self._count_tokens(chunk),
                    index=idx,
                )
            )

        return results
