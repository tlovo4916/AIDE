"""Anthropic/Claude LLM provider via httpx.

Supports Claude models (claude-opus-4-6, claude-sonnet-4-6, etc.)
with configurable base URL for proxies or custom deployments.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.config import settings
from backend.llm.models import LLMResponse

log = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://api.anthropic.com"
_API_VERSION = "2023-06-01"


class AnthropicProvider:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.anthropic_api_key or ""
        self._base_url = (base_url or settings.anthropic_base_url).rstrip("/")
        self._client = httpx.AsyncClient(
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": _API_VERSION,
                "Content-Type": "application/json",
            },
            timeout=600.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def call(
        self,
        messages: list[dict[str, str]],
        model: str = "claude-sonnet-4-6",
        temperature: float = 0.7,
        max_tokens: int = 8192,
        **kwargs: Any,
    ) -> LLMResponse:
        # Anthropic Messages API requires system prompt as a separate parameter
        system_prompt = ""
        api_messages: list[dict[str, str]] = []
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
            else:
                api_messages.append({"role": msg["role"], "content": msg["content"]})

        # Ensure at least one user message
        if not api_messages:
            api_messages.append({"role": "user", "content": ""})

        payload: dict[str, Any] = {
            "model": model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt

        log.info(
            "Anthropic call: model=%s, messages=%d, system=%d chars",
            model,
            len(api_messages),
            len(system_prompt),
        )

        resp = await self._client.post(
            f"{self._base_url}/v1/messages",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        # Extract content from response
        content_blocks = data.get("content", [])
        content = ""
        for block in content_blocks:
            if block.get("type") == "text":
                content += block.get("text", "")

        usage = data.get("usage", {})
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)

        log.info(
            "Anthropic response: model=%s, content_len=%d, prompt_tok=%d, compl_tok=%d",
            model,
            len(content),
            prompt_tokens,
            completion_tokens,
        )

        return LLMResponse(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=data.get("model", model),
        )
