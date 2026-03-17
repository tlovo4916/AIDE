from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

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
    "enable_llm_planner",
    "enable_write_back_guard",
    "topic_drift_embedding_threshold",
    "topic_drift_keyword_threshold",
    "max_iterations_per_phase",
    "convergence_min_critic_score",
]

_KEY_FIELDS = {
    "deepseek_api_key",
    "openrouter_api_key",
    "anthropic_api_key",
    "semantic_scholar_api_key",
}

# Migrate legacy short embedding model names to full OpenRouter paths
_EMBED_MIGRATION = {
    "text-embedding-3-small": "openai/text-embedding-3-small",
    "text-embedding-3-large": "openai/text-embedding-3-large",
}


def _overrides_path() -> Path:
    return settings.workspace_dir / "settings_overrides.json"


def _apply_overrides(data: dict) -> None:
    """Apply a dict of overrides to the global settings object."""
    if data.get("embedding_model") in _EMBED_MIGRATION:
        data["embedding_model"] = _EMBED_MIGRATION[data["embedding_model"]]
    for field in _OVERRIDES_FIELDS:
        if field not in data or data[field] is None:
            continue
        if isinstance(data[field], dict) and not data[field]:
            continue
        if field in _KEY_FIELDS and data[field] == "":
            continue
        setattr(settings, field, data[field])


def _load_json_overrides() -> dict | None:
    """Load overrides from JSON file (legacy)."""
    path = _overrides_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        logger.warning("Failed to load JSON overrides: %s", exc)
        return None


async def load_overrides() -> None:
    """Load settings overrides: try DB first, fall back to JSON file.

    If DB table is empty but JSON file exists, migrate settings to DB.
    """
    db_data: dict | None = None
    try:
        from backend.models import ProjectSetting, async_session_factory

        async with async_session_factory() as session:
            result = await session.execute(
                select(ProjectSetting).where(ProjectSetting.project_id.is_(None))
            )
            rows = result.scalars().all()
            if rows:
                db_data = {}
                for row in rows:
                    try:
                        db_data[row.key] = json.loads(row.value)
                    except (json.JSONDecodeError, TypeError):
                        db_data[row.key] = row.value
                _apply_overrides(db_data)
                logger.info("Settings loaded from DB (%d keys)", len(db_data))
                return
    except Exception as exc:
        logger.warning("Failed to load settings from DB: %s", exc)

    # Fall back to JSON file
    json_data = _load_json_overrides()
    if json_data:
        _apply_overrides(json_data)
        logger.info("Settings loaded from JSON file")
        # Migrate to DB on first load
        try:
            await _save_overrides_to_db(json_data)
            logger.info("Migrated JSON settings to DB")
        except Exception as exc:
            logger.warning("Failed to migrate JSON settings to DB: %s", exc)


async def _save_overrides_to_db(data: dict | None = None) -> None:
    """Upsert current settings into project_settings table (project_id=NULL for global)."""
    if data is None:
        data = {field: getattr(settings, field) for field in _OVERRIDES_FIELDS}
    try:
        from backend.models import ProjectSetting, async_session_factory

        async with async_session_factory() as session:
            for key, value in data.items():
                if key not in _OVERRIDES_FIELDS:
                    continue
                value_str = json.dumps(value, default=str)
                # Try to find existing
                result = await session.execute(
                    select(ProjectSetting).where(
                        ProjectSetting.project_id.is_(None),
                        ProjectSetting.key == key,
                    )
                )
                existing = result.scalar_one_or_none()
                if existing:
                    existing.value = value_str
                else:
                    session.add(ProjectSetting(project_id=None, key=key, value=value_str))
            await session.commit()
    except Exception as exc:
        logger.error("Failed to save settings to DB: %s", exc)


def _save_json_overrides() -> None:
    """Save current settings to JSON file (backup)."""
    path = _overrides_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {field: getattr(settings, field) for field in _OVERRIDES_FIELDS}
        path.write_text(json.dumps(data, default=str))
    except Exception as exc:
        logger.error("Failed to save JSON overrides: %s", exc)


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
    enable_llm_planner: bool = True
    enable_write_back_guard: bool = True
    topic_drift_embedding_threshold: float = 0.5
    topic_drift_keyword_threshold: float = 0.4
    max_iterations_per_phase: int = 4
    convergence_min_critic_score: float = 6.0


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
        enable_llm_planner=settings.enable_llm_planner,
        enable_write_back_guard=settings.enable_write_back_guard,
        topic_drift_embedding_threshold=settings.topic_drift_embedding_threshold,
        topic_drift_keyword_threshold=settings.topic_drift_keyword_threshold,
        max_iterations_per_phase=settings.max_iterations_per_phase,
        convergence_min_critic_score=settings.convergence_min_critic_score,
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
    settings.enable_llm_planner = body.enable_llm_planner
    settings.enable_write_back_guard = body.enable_write_back_guard
    settings.topic_drift_embedding_threshold = body.topic_drift_embedding_threshold
    settings.topic_drift_keyword_threshold = body.topic_drift_keyword_threshold
    settings.max_iterations_per_phase = body.max_iterations_per_phase
    settings.convergence_min_critic_score = body.convergence_min_critic_score

    # Save to both DB and JSON (JSON as fallback)
    await _save_overrides_to_db()
    _save_json_overrides()
    return await get_settings()
