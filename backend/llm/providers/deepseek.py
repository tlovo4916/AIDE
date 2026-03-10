"""DeepSeek LLM provider via httpx.

Ref: https://api-docs.deepseek.com/zh-cn/api/create-chat-completion
     https://api-docs.deepseek.com/zh-cn/guides/reasoning_model

deepseek-reasoner 注意事项:
  - 不支持 temperature / top_p / presence_penalty / frequency_penalty（设了不报错但不生效）
  - 不支持 logprobs / top_logprobs（会报错）
  - 不支持 Function Calling
  - 响应中 content 可为 null，reasoning_content 存放思维链
  - 多轮对话不能传入 reasoning_content 字段
  - max_tokens 默认 32K，最大 64K（含思维链）
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.config import settings
from backend.llm.models import LLMResponse

log = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"


class DeepSeekProvider:
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.deepseek_api_key or ""
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=600.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _is_reasoner(model: str) -> bool:
        return model == "deepseek-reasoner" or "reasoner" in model.lower()

    @staticmethod
    def _clean_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Strip reasoning_content from assistant messages to avoid 400 errors."""
        cleaned = []
        for msg in messages:
            m = dict(msg)
            m.pop("reasoning_content", None)
            cleaned.append(m)
        return cleaned

    async def call(
        self,
        messages: list[dict[str, str]],
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        is_reasoner = self._is_reasoner(model)

        clean_msgs = self._clean_messages(messages)

        payload: dict[str, Any] = {
            "model": model,
            "messages": clean_msgs,
            "stream": False,
        }

        if is_reasoner:
            payload["max_tokens"] = 16384
        else:
            payload["temperature"] = temperature
            payload["max_tokens"] = max_tokens
            if response_format:
                payload["response_format"] = response_format

        log.info(
            "DeepSeek call: model=%s, messages=%d, is_reasoner=%s",
            model,
            len(clean_msgs),
            is_reasoner,
        )

        resp = await self._client.post(DEEPSEEK_API_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        message = choice["message"]
        usage = data.get("usage", {})

        content = message.get("content") or ""
        reasoning_content = message.get("reasoning_content") or ""

        if not content and reasoning_content:
            content = reasoning_content

        if not content:
            log.warning(
                "DeepSeek returned empty content for model=%s, finish_reason=%s, reasoning_len=%d",
                model,
                choice.get("finish_reason"),
                len(reasoning_content),
            )

        log.info(
            "DeepSeek response: model=%s, finish=%s, content_len=%d, "
            "reasoning_len=%d, prompt_tok=%d, compl_tok=%d",
            model,
            choice.get("finish_reason"),
            len(content),
            len(reasoning_content),
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
        )

        return LLMResponse(
            content=content,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            model=data.get("model", model),
        )
