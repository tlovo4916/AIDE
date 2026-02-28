"""DeepSeek LLM provider via httpx."""

from __future__ import annotations

from typing import Any

import httpx

from backend.config import settings
from backend.llm.models import LLMResponse

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


class DeepSeekProvider:

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.deepseek_api_key or ""
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def call(
        self,
        messages: list[dict[str, str]],
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        resp = await self._client.post(DEEPSEEK_API_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        usage = data.get("usage", {})

        return LLMResponse(
            content=choice["message"]["content"],
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            model=data.get("model", model),
        )
