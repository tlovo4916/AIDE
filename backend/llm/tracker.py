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

# USD per 1K tokens
COST_PER_1K: dict[str, dict[str, float]] = {
    "deepseek-chat": {"prompt": 0.0014, "completion": 0.0028},
    "deepseek-reasoner": {"prompt": 0.0055, "completion": 0.0219},
    "gpt": {"prompt": 0.003, "completion": 0.012},
    "gemini-pro": {"prompt": 0.00125, "completion": 0.005},
    "claude-opus": {"prompt": 0.015, "completion": 0.075},
    "claude-sonnet": {"prompt": 0.003, "completion": 0.015},
    "claude-haiku": {"prompt": 0.0008, "completion": 0.004},
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
        rates = COST_PER_1K.get(key, {"prompt": 0.01, "completion": 0.03})
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
                async with self._session_factory() as session:
                    session.add(
                        TokenUsage(
                            project_id=uuid.UUID(project_id),
                            agent_role=agent_role.value,
                            model_name=model,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            total_tokens=prompt_tokens + completion_tokens,
                            cost_usd=cost,
                        )
                    )
                    await session.commit()
            except Exception as exc:
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
    model_lower = model.lower()
    # Exact prefix matches first (order matters for Claude model family)
    if "claude" in model_lower:
        if "haiku" in model_lower:
            return "claude-haiku"
        if "sonnet" in model_lower:
            return "claude-sonnet"
        return "claude-opus"
    for key in COST_PER_1K:
        if key in model_lower:
            return key
    if "gemini" in model_lower:
        return "gemini-pro"
    if "gpt" in model_lower:
        return "gpt"
    return "deepseek-chat"
