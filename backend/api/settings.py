from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from backend.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])

_OVERRIDES_FIELDS = [
    "deepseek_api_key",
    "openrouter_api_key",
    "anthropic_api_key",
    "anthropic_base_url",
    "semantic_scholar_api_key",
    "embedding_model",
    "summarizer_model",
    "enable_web_retrieval",
    "agent_model_overrides",
    "custom_presets",
]


def _overrides_path() -> Path:
    return settings.workspace_dir / "settings_overrides.json"


def load_overrides() -> None:
    """从持久化文件加载设置覆盖，在启动时调用。"""
    path = _overrides_path()
    if not path.exists():
        return
    try:
        data: dict = json.loads(path.read_text())
        # Migrate legacy short embedding model names to full OpenRouter paths
        _EMBED_MIGRATION = {
            "text-embedding-3-small": "openai/text-embedding-3-small",
            "text-embedding-3-large": "openai/text-embedding-3-large",
        }
        if data.get("embedding_model") in _EMBED_MIGRATION:
            data["embedding_model"] = _EMBED_MIGRATION[data["embedding_model"]]
        _KEY_FIELDS = {"deepseek_api_key", "openrouter_api_key", "anthropic_api_key",
                       "semantic_scholar_api_key"}
        for field in _OVERRIDES_FIELDS:
            if field not in data or data[field] is None:
                continue
            # 空 dict / 空字符串 key 不覆盖（保留 .env 中的真实值）
            if isinstance(data[field], dict) and not data[field]:
                continue
            if field in _KEY_FIELDS and data[field] == "":
                continue
            setattr(settings, field, data[field])
        logger.info("Settings overrides loaded from %s", path)
    except Exception as exc:
        logger.warning("Failed to load settings overrides: %s", exc)


def _save_overrides() -> None:
    """将当前设置持久化到 workspace volume。"""
    path = _overrides_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {field: getattr(settings, field) for field in _OVERRIDES_FIELDS}
        path.write_text(json.dumps(data, default=str))
    except Exception as exc:
        logger.error("Failed to save settings overrides: %s", exc)


class LLMSettings(BaseModel):
    deepseek_api_key: str | None = None
    openrouter_api_key: str | None = None
    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com"
    embedding_model: str = "qwen/qwen3-embedding-4b"
    summarizer_model: str = "deepseek-chat"
    enable_web_retrieval: bool = False
    semantic_scholar_api_key: str | None = None
    agent_model_overrides: dict[str, str] = {
        "director": "deepseek-reasoner",
        "scientist": "deepseek-reasoner",
        "critic": "deepseek-reasoner",
        "librarian": "deepseek-chat",
        "writer": "deepseek-chat",
        "synthesizer": "deepseek-reasoner",
    }
    custom_presets: dict[str, dict] = {}


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
        anthropic_api_key=_mask(settings.anthropic_api_key),
        anthropic_base_url=settings.anthropic_base_url,
        embedding_model=settings.embedding_model,
        summarizer_model=settings.summarizer_model,
        enable_web_retrieval=settings.enable_web_retrieval,
        semantic_scholar_api_key=_mask(settings.semantic_scholar_api_key),
        agent_model_overrides=settings.agent_model_overrides,
        custom_presets=settings.custom_presets,
    )


@router.put("", response_model=LLMSettings)
async def update_settings(body: LLMSettings) -> LLMSettings:
    if body.deepseek_api_key and "****" not in body.deepseek_api_key:
        settings.deepseek_api_key = body.deepseek_api_key
    if body.openrouter_api_key and "****" not in body.openrouter_api_key:
        settings.openrouter_api_key = body.openrouter_api_key
    if body.semantic_scholar_api_key and "****" not in body.semantic_scholar_api_key:
        settings.semantic_scholar_api_key = body.semantic_scholar_api_key
    if body.anthropic_api_key and "****" not in body.anthropic_api_key:
        settings.anthropic_api_key = body.anthropic_api_key
    if body.anthropic_base_url:
        settings.anthropic_base_url = body.anthropic_base_url

    settings.embedding_model = body.embedding_model
    settings.summarizer_model = body.summarizer_model
    settings.enable_web_retrieval = body.enable_web_retrieval
    settings.agent_model_overrides = body.agent_model_overrides
    settings.custom_presets = body.custom_presets

    _save_overrides()
    return await get_settings()
