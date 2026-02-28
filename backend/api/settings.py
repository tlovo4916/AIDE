from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.config import settings

router = APIRouter(prefix="/settings", tags=["settings"])


class LLMSettings(BaseModel):
    deepseek_api_key: str | None = None
    openrouter_api_key: str | None = None
    openai_api_key: str | None = None
    default_model: str = "deepseek-reasoner"
    embedding_model: str = "text-embedding-3-small"
    summarizer_model: str = "deepseek-chat"
    enable_web_retrieval: bool = False
    semantic_scholar_api_key: str | None = None


def _mask(key: str | None) -> str | None:
    if not key:
        return None
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


@router.get("", response_model=LLMSettings)
async def get_settings() -> LLMSettings:
    return LLMSettings(
        deepseek_api_key=_mask(settings.deepseek_api_key),
        openrouter_api_key=_mask(settings.openrouter_api_key),
        openai_api_key=_mask(settings.openai_api_key),
        default_model=settings.default_model,
        embedding_model=settings.embedding_model,
        summarizer_model=settings.summarizer_model,
        enable_web_retrieval=settings.enable_web_retrieval,
        semantic_scholar_api_key=_mask(settings.semantic_scholar_api_key),
    )


@router.put("", response_model=LLMSettings)
async def update_settings(body: LLMSettings) -> LLMSettings:
    if body.deepseek_api_key and "****" not in body.deepseek_api_key:
        settings.deepseek_api_key = body.deepseek_api_key
    if body.openrouter_api_key and "****" not in body.openrouter_api_key:
        settings.openrouter_api_key = body.openrouter_api_key
    if body.openai_api_key and "****" not in body.openai_api_key:
        settings.openai_api_key = body.openai_api_key
    if body.semantic_scholar_api_key and "****" not in body.semantic_scholar_api_key:
        settings.semantic_scholar_api_key = body.semantic_scholar_api_key

    settings.default_model = body.default_model
    settings.embedding_model = body.embedding_model
    settings.summarizer_model = body.summarizer_model
    settings.enable_web_retrieval = body.enable_web_retrieval

    return await get_settings()
