"""Vector store backed by ChromaDB PersistentClient."""

from __future__ import annotations

from typing import Any

import chromadb  # type: ignore[import-untyped]

from backend.config import settings


class VectorStore:

    def __init__(
        self,
        persist_dir: str | None = None,
        collection_name: str | None = None,
    ) -> None:
        self._persist_dir = persist_dir or str(settings.chroma_persist_dir)
        self._default_collection = collection_name or settings.chroma_collection
        self._client = chromadb.PersistentClient(path=self._persist_dir)
        self._collection: chromadb.Collection | None = None

    def init_collection(self, collection_name: str | None = None) -> None:
        name = collection_name or self._default_collection
        self._collection = self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            self.init_collection()
        assert self._collection is not None
        return self._collection

    def add_documents(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query(
        self,
        query_embeddings: list[list[float]],
        n_results: int = 10,
        where_filter: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "query_embeddings": query_embeddings,
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter:
            kwargs["where"] = where_filter
        return self.collection.query(**kwargs)

    def delete_by_source(self, source_id: str) -> None:
        self.collection.delete(where={"source_file": source_id})

    def count(self) -> int:
        return self.collection.count()
