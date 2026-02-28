"""Shared LLM response model."""

from __future__ import annotations

from pydantic import BaseModel


class LLMResponse(BaseModel):
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
