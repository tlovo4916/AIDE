"""Embedding service via OpenRouter embedding API."""

from __future__ import annotations

import logging

import httpx
import tiktoken

from backend.config import settings

logger = logging.getLogger(__name__)

# Legacy short name → OpenRouter full model ID (new configs use full IDs directly)
_MODEL_MAP: dict[str, str] = {
    "text-embedding-3-small": "openai/text-embedding-3-small",
    "text-embedding-3-large": "openai/text-embedding-3-large",
    "text-embedding-ada-002": "openai/text-embedding-ada-002",
}

# Default model (OpenRouter full ID)
_DEFAULT_MODEL = "openai/text-embedding-3-small"


class EmbeddingService:
    MODEL = "text-embedding-3-small"  # for tiktoken encoder only
    MAX_TOKENS = 8191
    BATCH_LIMIT = 2048

    def __init__(self, model: str | None = None) -> None:
        self._api_key = settings.openrouter_api_key or ""
        self._model_override = model
        self._encoder = tiktoken.encoding_for_model(self.MODEL)
        self._client = httpx.AsyncClient(
            base_url="https://openrouter.ai/api/v1",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://aide.local",
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

        model = self._model_override or settings.embedding_model or _DEFAULT_MODEL
        model = _MODEL_MAP.get(model, model)  # resolve legacy short names

        for start in range(0, len(truncated), self.BATCH_LIMIT):
            batch = truncated[start : start + self.BATCH_LIMIT]
            resp = await self._client.post(
                "/embeddings",
                json={
                    "input": batch,
                    "model": model,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            sorted_data = sorted(data["data"], key=lambda x: x["index"])
            all_embeddings.extend([item["embedding"] for item in sorted_data])

        return all_embeddings
