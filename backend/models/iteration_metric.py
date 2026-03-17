"""IterationMetric ORM model -- per-iteration measurements."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models import Base


class IterationMetric(Base):
    __tablename__ = "iteration_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phase: Mapped[str] = mapped_column(String(50), nullable=False)
    iteration: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    artifacts_produced: Mapped[int | None] = mapped_column(Integer, nullable=True)
    critic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    information_gain: Mapped[float | None] = mapped_column(Float, nullable=True)
    artifact_count_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unique_claim_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eval_composite: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
