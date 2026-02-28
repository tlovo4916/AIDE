from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import get_session, Project

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
    metadata: dict


def _papers_dir(project_id: uuid.UUID) -> Path:
    return settings.project_path(str(project_id)) / "papers"


@router.post("/upload", response_model=PaperOut, status_code=201)
async def upload_paper(
    project_id: uuid.UUID,
    file: UploadFile,
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

    # TODO: trigger async PDF processing pipeline (chunking + embedding)

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

    # TODO: remove chunks from ChromaDB


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

    # TODO: implement hybrid search (BM25 + vector) via knowledge layer
    return []
