"""Embedding service using OpenAI text-embedding-3-small."""

from __future__ import annotations

import tiktoken
import httpx

from backend.config import settings


class EmbeddingService:

    MODEL = "text-embedding-3-small"
    MAX_TOKENS = 8191
    BATCH_LIMIT = 2048

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.openai_api_key or ""
        self._encoder = tiktoken.encoding_for_model(self.MODEL)
        self._client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    def count_tokens(self, text: str) -> int:
        return len(self._encoder.encode(text))

    def _truncate(self, text: str) -> str:
        tokens = self._encoder.encode(text)
        if len(tokens) > self.MAX_TOKENS:
            tokens = tokens[: self.MAX_TOKENS]
            return self._encoder.decode(tokens)
        return text

    async def embed_text(self, text: str) -> list[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        truncated = [self._truncate(t) for t in texts]
        all_embeddings: list[list[float]] = []

        for start in range(0, len(truncated), self.BATCH_LIMIT):
            batch = truncated[start : start + self.BATCH_LIMIT]
            resp = await self._client.post(
                "/embeddings",
                json={
                    "input": batch,
                    "model": settings.embedding_model or self.MODEL,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            sorted_data = sorted(data["data"], key=lambda x: x["index"])
            all_embeddings.extend([item["embedding"] for item in sorted_data])

        return all_embeddings
