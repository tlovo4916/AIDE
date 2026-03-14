"""Token usage tracking and cost estimation."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.types import AgentRole

logger = logging.getLogger(__name__)

# USD per 1K tokens — sourced from price_design.md (2026-03-13)
COST_PER_1K: dict[str, dict[str, float]] = {
    # ── DeepSeek (direct API, 官网价: input 2元/M, output 3元/M) ──
    "deepseek-chat": {"prompt": 0.00028, "completion": 0.00041},
    "deepseek-reasoner": {"prompt": 0.00028, "completion": 0.00041},
    # ── DeepSeek V3.2 Speciale (OpenRouter only) ──
    "deepseek-v3.2-speciale": {"prompt": 0.0004, "completion": 0.0012},
    # ── Anthropic (direct API) ──
    "claude-opus": {"prompt": 0.005, "completion": 0.025},
    "claude-sonnet": {"prompt": 0.003, "completion": 0.015},
    "claude-haiku": {"prompt": 0.0008, "completion": 0.004},
    # ── OpenAI (via OpenRouter) ──
    "gpt-5.4": {"prompt": 0.0025, "completion": 0.015},
    "gpt-5.4-pro": {"prompt": 0.030, "completion": 0.180},
    "gpt-5-nano": {"prompt": 0.00005, "completion": 0.0004},
    # ── Google (via OpenRouter) ──
    "gemini-3.1-pro": {"prompt": 0.002, "completion": 0.012},
    # ── xAI (via OpenRouter) ──
    "grok-4": {"prompt": 0.003, "completion": 0.015},
    "grok-4.1-fast": {"prompt": 0.0002, "completion": 0.0005},
    # ── Qwen (via OpenRouter) ──
    "qwen3.5-plus": {"prompt": 0.00026, "completion": 0.00156},
    "qwen3.5-flash": {"prompt": 0.0001, "completion": 0.0004},
    "qwen3.5-397b": {"prompt": 0.00039, "completion": 0.00234},
    # ── Step (via OpenRouter) ──
    "step-3.5-flash": {"prompt": 0.0001, "completion": 0.0003},
    # ── MiniMax (via OpenRouter) ──
    "minimax-m2.5": {"prompt": 0.00027, "completion": 0.00095},
    # ── 智谱 GLM (via OpenRouter) ──
    "glm-5": {"prompt": 0.00072, "completion": 0.0023},
    "glm-4.7-flash": {"prompt": 0.00006, "completion": 0.0004},
    # ── 月之暗面 (via OpenRouter) ──
    "kimi-k2.5": {"prompt": 0.00045, "completion": 0.0022},
    # ── 字节跳动 (via OpenRouter) ──
    "seed-1.6-flash": {"prompt": 0.000075, "completion": 0.0003},
    # ── Meta (via OpenRouter) ──
    "llama-4-maverick": {"prompt": 0.00015, "completion": 0.0006},
    # ── 小米 (via OpenRouter) ──
    "mimo-v2-flash": {"prompt": 0.00009, "completion": 0.00029},
    # ── Legacy aliases ──
    "gpt": {"prompt": 0.0025, "completion": 0.015},
    "gemini-pro": {"prompt": 0.002, "completion": 0.012},
}

USD_TO_RMB = 7.24


class TokenTracker:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        self._session_factory = session_factory
        self._memory_log: list[dict[str, Any]] = []

    @staticmethod
    def get_cost_estimate(
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        key = _resolve_cost_key(model)
        rates = COST_PER_1K.get(key, {"prompt": 0.001, "completion": 0.003})
        return (
            prompt_tokens / 1000 * rates["prompt"] + completion_tokens / 1000 * rates["completion"]
        )

    async def record_usage(
        self,
        project_id: str,
        agent_role: AgentRole,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        cost = self.get_cost_estimate(model, prompt_tokens, completion_tokens)
        record = {
            "project_id": project_id,
            "agent_role": agent_role.value,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost": cost,
            "created_at": datetime.utcnow().isoformat(),
        }
        self._memory_log.append(record)

        if self._session_factory:
            from backend.models.token_usage import TokenUsage

            try:
                pid = uuid.UUID(project_id)
            except (ValueError, AttributeError):
                logger.warning("Invalid project_id for token tracking: %r", project_id)
                return

            try:
                async with self._session_factory() as session:
                    session.add(
                        TokenUsage(
                            project_id=pid,
                            agent_role=agent_role.value,
                            model_name=model,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            total_tokens=prompt_tokens + completion_tokens,
                            cost_usd=cost,
                        )
                    )
                    try:
                        await session.commit()
                    except Exception:
                        await session.rollback()
                        raise
            except Exception as exc:
                # ForeignKeyViolation can happen if project was deleted mid-run
                logger.warning("Failed to persist token usage to DB: %s", exc)

    async def get_project_usage(self, project_id: str) -> dict[str, Any]:
        by_model: dict[str, dict[str, Any]] = {}

        if self._session_factory:
            from backend.models.token_usage import TokenUsage

            try:
                async with self._session_factory() as session:
                    stmt = (
                        select(
                            TokenUsage.model_name,
                            func.sum(TokenUsage.prompt_tokens).label("total_prompt"),
                            func.sum(TokenUsage.completion_tokens).label("total_completion"),
                            func.sum(TokenUsage.cost_usd).label("total_cost"),
                            func.count().label("call_count"),
                        )
                        .where(TokenUsage.project_id == uuid.UUID(project_id))
                        .group_by(TokenUsage.model_name)
                    )
                    result = await session.execute(stmt)
                    rows = result.all()
                    by_model = {
                        row.model_name: {
                            "prompt_tokens": int(row.total_prompt or 0),
                            "completion_tokens": int(row.total_completion or 0),
                            "total_tokens": int(
                            (row.total_prompt or 0) + (row.total_completion or 0)
                        ),
                            "cost_usd": round(float(row.total_cost or 0.0), 6),
                            "calls": int(row.call_count),
                        }
                        for row in rows
                    }
            except Exception as exc:
                logger.warning("Failed to query token usage from DB: %s", exc)

        if not by_model:
            records = [r for r in self._memory_log if r["project_id"] == project_id]
            for r in records:
                m = r["model"]
                if m not in by_model:
                    by_model[m] = {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "cost_usd": 0.0,
                        "calls": 0,
                    }
                by_model[m]["prompt_tokens"] += r["prompt_tokens"]
                by_model[m]["completion_tokens"] += r["completion_tokens"]
                by_model[m]["total_tokens"] += r["prompt_tokens"] + r["completion_tokens"]
                by_model[m]["cost_usd"] += r["cost"]
                by_model[m]["calls"] += 1

        total_prompt = sum(m["prompt_tokens"] for m in by_model.values())
        total_completion = sum(m["completion_tokens"] for m in by_model.values())
        total_tokens = total_prompt + total_completion
        total_cost_usd = round(sum(m["cost_usd"] for m in by_model.values()), 6)
        total_cost_rmb = round(total_cost_usd * USD_TO_RMB, 4)
        total_calls = sum(m["calls"] for m in by_model.values())

        return {
            "project_id": project_id,
            "by_model": by_model,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost_usd,
            "total_cost_rmb": total_cost_rmb,
            "total_calls": total_calls,
        }


def _resolve_cost_key(model: str) -> str:
    ml = model.lower()
    # Claude family
    if "claude" in ml:
        if "haiku" in ml:
            return "claude-haiku"
        if "sonnet" in ml:
            return "claude-sonnet"
        return "claude-opus"
    # DeepSeek family
    if "speciale" in ml:
        return "deepseek-v3.2-speciale"
    if "deepseek-reasoner" in ml:
        return "deepseek-reasoner"
    if "deepseek" in ml:
        return "deepseek-chat"
    # Step
    if "step" in ml and "flash" in ml:
        return "step-3.5-flash"
    # Qwen family
    if "qwen3.5-plus" in ml or "qwen/qwen3.5-plus" in ml:
        return "qwen3.5-plus"
    if "qwen3.5-flash" in ml or "qwen/qwen3.5-flash" in ml:
        return "qwen3.5-flash"
    if "qwen3.5-397b" in ml or "qwen/qwen3.5-397b" in ml:
        return "qwen3.5-397b"
    # MiniMax
    if "minimax" in ml or "m2.5" in ml:
        return "minimax-m2.5"
    # GLM family
    if "glm-5" in ml:
        return "glm-5"
    if "glm-4" in ml or "glm-4.7" in ml:
        return "glm-4.7-flash"
    # Moonshot
    if "kimi" in ml:
        return "kimi-k2.5"
    # ByteDance
    if "seed" in ml:
        return "seed-1.6-flash"
    # Xiaomi
    if "mimo" in ml:
        return "mimo-v2-flash"
    # Meta
    if "maverick" in ml or "llama-4" in ml:
        return "llama-4-maverick"
    # xAI Grok
    if "grok-4.1" in ml:
        return "grok-4.1-fast"
    if "grok" in ml:
        return "grok-4"
    # OpenAI
    if "gpt-5.4-pro" in ml:
        return "gpt-5.4-pro"
    if "gpt-5-nano" in ml or "gpt5-nano" in ml:
        return "gpt-5-nano"
    if "gpt-5.4" in ml:
        return "gpt-5.4"
    if "gpt" in ml:
        return "gpt-5.4"
    # Google
    if "gemini" in ml:
        return "gemini-3.1-pro"
    # Exact key match fallback
    for key in COST_PER_1K:
        if key in ml:
            return key
    return "deepseek-chat"
