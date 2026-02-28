from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import get_session, Project

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/papers", tags=["papers"])


class PaperOut(BaseModel):
    filename: str
    size_bytes: int
    paper_id: str


class SearchHit(BaseModel):
    chunk_id: str
    content: str
    source: str
    score: float
    metadata: dict[str, Any]


def _papers_dir(project_id: uuid.UUID) -> Path:
    return settings.project_path(str(project_id)) / "papers"


def _get_bm25_store(project_id: uuid.UUID):
    from backend.knowledge.bm25_store import BM25Store
    store = BM25Store(persist_path=str(settings.project_path(str(project_id)) / "bm25_index.json"))
    store.load()
    return store


def _get_vector_store(project_id: uuid.UUID):
    from backend.knowledge.vector_store import VectorStore
    collection_name = f"aide_{str(project_id).replace('-', '_')}"
    store = VectorStore(collection_name=collection_name)
    return store


async def _process_pdf(pdf_path: Path, paper_id: str, project_id: uuid.UUID) -> None:
    """Background task: extract text, chunk, embed, index."""
    try:
        from backend.knowledge.pdf_processor import PDFProcessor
        from backend.knowledge.embeddings import EmbeddingService
        from backend.llm.router import LLMRouter

        llm_router = LLMRouter()

        async def summarizer(style: str, prompt: str) -> str:
            return await llm_router.generate(
                settings.summarizer_model, prompt,
                system_prompt="You are a concise summarizer. Output only the summary."
            )

        processor = PDFProcessor(summarizer=summarizer)
        chunks = await processor.process(pdf_path)

        if not chunks:
            logger.warning("No chunks produced from %s", pdf_path)
            return

        vector_store = _get_vector_store(project_id)
        bm25_store = _get_bm25_store(project_id)

        chunk_ids = [c.chunk_id for c in chunks]
        chunk_texts = [c.content for c in chunks]
        chunk_metadatas = [
            {**c.metadata, "source_file": paper_id, "paper_id": paper_id}
            for c in chunks
        ]

        embedding_service = EmbeddingService()
        try:
            embeddings = await embedding_service.embed_batch(chunk_texts)
            vector_store.add_documents(
                ids=chunk_ids,
                embeddings=embeddings,
                documents=chunk_texts,
                metadatas=chunk_metadatas,
            )
        except Exception as exc:
            logger.warning("Embedding/vector indexing failed (will still index BM25): %s", exc)
        finally:
            await embedding_service.close()

        bm25_store.add_documents(chunk_ids, chunk_texts)
        bm25_store.save()

        await llm_router.close()
        logger.info("PDF processing complete for %s: %d chunks indexed", paper_id, len(chunks))

    except Exception:
        logger.exception("PDF processing failed for %s", paper_id)


@router.post("/upload", response_model=PaperOut, status_code=201)
async def upload_paper(
    project_id: uuid.UUID,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> PaperOut:
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")

    paper_id = str(uuid.uuid4())
    dest_dir = _papers_dir(project_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{paper_id}.pdf"

    content = await file.read()
    dest.write_bytes(content)

    background_tasks.add_task(_process_pdf, dest, paper_id, project_id)

    return PaperOut(
        filename=file.filename,
        size_bytes=len(content),
        paper_id=paper_id,
    )


@router.get("", response_model=list[PaperOut])
async def list_papers(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[PaperOut]:
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    papers_dir = _papers_dir(project_id)
    if not papers_dir.exists():
        return []

    results: list[PaperOut] = []
    for pdf_file in papers_dir.glob("*.pdf"):
        results.append(
            PaperOut(
                filename=pdf_file.name,
                size_bytes=pdf_file.stat().st_size,
                paper_id=pdf_file.stem,
            )
        )
    return results


@router.delete("/{paper_id}", status_code=204)
async def delete_paper(
    project_id: uuid.UUID,
    paper_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    pdf_path = _papers_dir(project_id) / f"{paper_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(404, "Paper not found")
    pdf_path.unlink()

    try:
        vector_store = _get_vector_store(project_id)
        vector_store.delete_by_source(paper_id)
    except Exception as exc:
        logger.warning("Failed to clean ChromaDB for paper %s: %s", paper_id, exc)

    try:
        bm25_store = _get_bm25_store(project_id)
        ids_to_remove = {did for did in bm25_store._doc_ids if paper_id in did}
        if ids_to_remove:
            bm25_store.remove_documents(ids_to_remove)
            bm25_store.save()
    except Exception as exc:
        logger.warning("Failed to clean BM25 for paper %s: %s", paper_id, exc)


@router.get("/search", response_model=list[SearchHit])
async def search_papers(
    project_id: uuid.UUID,
    q: str = Query(..., min_length=1),
    top_k: int = Query(default=10, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[SearchHit]:
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    from backend.knowledge.hybrid_search import HybridSearchEngine
    from backend.knowledge.embeddings import EmbeddingService

    vector_store = _get_vector_store(project_id)
    bm25_store = _get_bm25_store(project_id)
    embedding_service = EmbeddingService()

    try:
        engine = HybridSearchEngine(vector_store, bm25_store, embedding_service)
        results = await engine.search([q], top_k=top_k)
    except Exception as exc:
        logger.warning("Hybrid search failed, returning empty: %s", exc)
        return []
    finally:
        await embedding_service.close()

    return [
        SearchHit(
            chunk_id=r.chunk_id,
            content=r.content,
            source=r.source,
            score=r.score,
            metadata=r.metadata,
        )
        for r in results
    ]
