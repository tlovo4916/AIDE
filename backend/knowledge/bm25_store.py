"""BM25 sparse retrieval index with JSON persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

from backend.config import settings


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


class BM25Store:
    def __init__(self, persist_path: str | None = None) -> None:
        self._persist_path = Path(persist_path or str(settings.workspace_dir / "bm25_index.json"))
        self._doc_ids: list[str] = []
        self._doc_texts: list[str] = []
        self._corpus: list[list[str]] = []
        self._index: BM25Okapi | None = None

    @property
    def size(self) -> int:
        return len(self._doc_ids)

    def _rebuild(self) -> None:
        if self._corpus:
            self._index = BM25Okapi(self._corpus)
        else:
            self._index = None

    def add_documents(self, doc_ids: list[str], texts: list[str]) -> None:
        for did, text in zip(doc_ids, texts):
            if did in self._doc_ids:
                continue
            self._doc_ids.append(did)
            self._doc_texts.append(text)
            self._corpus.append(_tokenize(text))
        self._rebuild()

    def remove_documents(self, doc_ids: set[str]) -> None:
        keep = [
            (did, txt, tok)
            for did, txt, tok in zip(self._doc_ids, self._doc_texts, self._corpus)
            if did not in doc_ids
        ]
        if keep:
            self._doc_ids, self._doc_texts, self._corpus = (
                [k[0] for k in keep],
                [k[1] for k in keep],
                [k[2] for k in keep],
            )
        else:
            self._doc_ids, self._doc_texts, self._corpus = [], [], []
        self._rebuild()

    def rebuild_index(self) -> None:
        self._corpus = [_tokenize(t) for t in self._doc_texts]
        self._rebuild()

    def query(self, query_text: str, n_results: int = 10) -> list[tuple[str, float]]:
        if not self._index or not self._doc_ids:
            return []
        tokens = _tokenize(query_text)
        scores = self._index.get_scores(tokens)
        ranked = sorted(zip(self._doc_ids, scores), key=lambda x: x[1], reverse=True)
        return ranked[:n_results]

    def save(self) -> None:
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {
            "doc_ids": self._doc_ids,
            "doc_texts": self._doc_texts,
        }
        self._persist_path.write_text(json.dumps(data, ensure_ascii=False))

    def load(self) -> None:
        if not self._persist_path.exists():
            return
        data = json.loads(self._persist_path.read_text())
        self._doc_ids = data.get("doc_ids", [])
        self._doc_texts = data.get("doc_texts", [])
        self._corpus = [_tokenize(t) for t in self._doc_texts]
        self._rebuild()
