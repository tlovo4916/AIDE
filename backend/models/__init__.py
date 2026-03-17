from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:  # type: ignore[misc]
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Create tables from ORM metadata.

    NOTE: Alembic migrations (backend/migrations/) are the source of truth
    for schema changes. ``create_all`` is kept here for dev convenience
    (auto-creates tables on first run without running ``alembic upgrade``).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# -- Existing models --
# -- Phase 1 models --
from backend.models.artifact import Artifact, ArtifactRelation  # noqa: E402, F401
from backend.models.challenge import Challenge  # noqa: E402, F401
from backend.models.checkpoint import Checkpoint  # noqa: E402, F401
from backend.models.claim import Claim, Contradiction  # noqa: E402, F401
from backend.models.evaluation import EvaluationResult, KnowledgeState  # noqa: E402, F401
from backend.models.info_request import InfoRequest  # noqa: E402, F401
from backend.models.iteration_metric import IterationMetric  # noqa: E402, F401
from backend.models.message import Message  # noqa: E402, F401
from backend.models.project import Project  # noqa: E402, F401
from backend.models.project_setting import ProjectSetting  # noqa: E402, F401
from backend.models.token_usage import TokenUsage  # noqa: E402, F401

__all__ = [
    "Base",
    "engine",
    "async_session_factory",
    "get_session",
    "init_db",
    # Existing
    "Project",
    "Checkpoint",
    "TokenUsage",
    # Phase 1
    "Artifact",
    "ArtifactRelation",
    "Challenge",
    "Claim",
    "Contradiction",
    "EvaluationResult",
    "InfoRequest",
    "IterationMetric",
    "KnowledgeState",
    "Message",
    "ProjectSetting",
]
