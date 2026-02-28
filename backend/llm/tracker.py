"""Token usage tracking and cost estimation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Awaitable

from sqlalchemy import Column, String, Integer, Float, DateTime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import select, func

from backend.types import AgentRole

COST_PER_1K: dict[str, dict[str, float]] = {
    "deepseek-chat":       {"prompt": 0.0014, "completion": 0.0028},
    "deepseek-reasoner":   {"prompt": 0.0055, "completion": 0.0219},
    "gpt":                 {"prompt": 0.003,  "completion": 0.012},
    "gemini-pro":          {"prompt": 0.00125,"completion": 0.005},
    "opus":                {"prompt": 0.015,  "completion": 0.075},
}


class Base(DeclarativeBase):
    pass


class TokenUsage(Base):
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, nullable=False, index=True)
    agent_role = Column(String, nullable=False)
    model = Column(String, nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


SessionFactory = Callable[[], Awaitable[AsyncSession]]


class TokenTracker:

    def __init__(self, session_factory: SessionFactory | None = None) -> None:
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
            prompt_tokens / 1000 * rates["prompt"]
            + completion_tokens / 1000 * rates["completion"]
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
            async with await self._session_factory() as session:
                session.add(
                    TokenUsage(
                        project_id=project_id,
                        agent_role=agent_role.value,
                        model=model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        cost=cost,
                    )
                )
                await session.commit()

    async def get_project_usage(self, project_id: str) -> dict[str, Any]:
        if self._session_factory:
            async with await self._session_factory() as session:
                stmt = (
                    select(
                        TokenUsage.model,
                        func.sum(TokenUsage.prompt_tokens).label("total_prompt"),
                        func.sum(TokenUsage.completion_tokens).label("total_completion"),
                        func.sum(TokenUsage.cost).label("total_cost"),
                        func.count().label("call_count"),
                    )
                    .where(TokenUsage.project_id == project_id)
                    .group_by(TokenUsage.model)
                )
                result = await session.execute(stmt)
                rows = result.all()
                by_model = {
                    row.model: {
                        "prompt_tokens": row.total_prompt,
                        "completion_tokens": row.total_completion,
                        "cost": round(row.total_cost, 6),
                        "calls": row.call_count,
                    }
                    for row in rows
                }
                total_cost = sum(m["cost"] for m in by_model.values())
                return {"project_id": project_id, "by_model": by_model, "total_cost": round(total_cost, 6)}

        records = [r for r in self._memory_log if r["project_id"] == project_id]
        by_model: dict[str, dict[str, Any]] = {}
        for r in records:
            m = r["model"]
            if m not in by_model:
                by_model[m] = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0, "calls": 0}
            by_model[m]["prompt_tokens"] += r["prompt_tokens"]
            by_model[m]["completion_tokens"] += r["completion_tokens"]
            by_model[m]["cost"] += r["cost"]
            by_model[m]["calls"] += 1
        total_cost = sum(m["cost"] for m in by_model.values())
        return {"project_id": project_id, "by_model": by_model, "total_cost": round(total_cost, 6)}


def _resolve_cost_key(model: str) -> str:
    model_lower = model.lower()
    for key in COST_PER_1K:
        if key in model_lower:
            return key
    if "claude" in model_lower or "opus" in model_lower:
        return "opus"
    if "gemini" in model_lower:
        return "gemini-pro"
    if "gpt" in model_lower:
        return "gpt"
    return "deepseek-chat"
