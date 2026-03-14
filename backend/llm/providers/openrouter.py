"""OpenRouter LLM provider via httpx."""

from __future__ import annotations

from typing import Any

import httpx

from backend.config import settings
from backend.llm.models import LLMResponse

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

MODEL_MAP: dict[str, str] = {
    # --- Frontier ---
    "gpt-5.4": "openai/gpt-5.4",
    "gpt-5.4-pro": "openai/gpt-5.4-pro",
    "gemini-3.1-pro": "google/gemini-3.1-pro-preview",
    "grok-4": "x-ai/grok-4",
    # --- Value / Mid-tier ---
    "qwen3.5-plus": "qwen/qwen3.5-plus-02-15",
    "minimax-m2.5": "minimax/minimax-m2.5",
    "glm-5": "z-ai/glm-5",
    "deepseek-v3.2-speciale": "deepseek/deepseek-v3.2-speciale",
    "grok-4.1-fast": "x-ai/grok-4.1-fast",
    "kimi-k2.5": "moonshotai/kimi-k2.5",
    "qwen3.5-flash": "qwen/qwen3.5-flash-02-23",
    "qwen3.5-397b": "qwen/qwen3.5-397b-a17b",
    # --- Budget ---
    "step-3.5-flash": "stepfun/step-3.5-flash:free",
    "seed-1.6-flash": "bytedance-seed/seed-1.6-flash",
    "gpt-5-nano": "openai/gpt-5-nano",
    "glm-4.7-flash": "z-ai/glm-4.7-flash",
    "mimo-v2-flash": "xiaomi/mimo-v2-flash",
    "llama-4-maverick": "meta-llama/llama-4-maverick",
    # --- Legacy aliases ---
    "gemini-pro": "google/gemini-3.1-pro-preview",
    "gpt": "openai/gpt-5.4",
    "opus": "anthropic/claude-opus-4",
}


class OpenRouterProvider:
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.openrouter_api_key or ""
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://aide.local",
            },
            timeout=120.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    def resolve_model(self, model: str) -> str:
        return MODEL_MAP.get(model, model)

    async def call(
        self,
        messages: list[dict[str, str]],
        model: str = "gemini-pro",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        resolved = self.resolve_model(model)
        payload: dict[str, Any] = {
            "model": resolved,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        resp = await self._client.post(OPENROUTER_API_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        usage = data.get("usage", {})

        return LLMResponse(
            content=choice["message"]["content"],
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            model=data.get("model", resolved),
        )
