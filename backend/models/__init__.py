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
    import logging

    _logger = logging.getLogger(__name__)

    async with engine.begin() as conn:
        # pgvector extension must exist before create_all (vector columns depend on it)
        await conn.execute(
            __import__("sqlalchemy").text(
                "CREATE EXTENSION IF NOT EXISTS vector"
            )
        )
        await conn.run_sync(Base.metadata.create_all)

        # Ensure embedding vector columns exist (create_all skips them because
        # they are not mapped in ORM — added via raw SQL in Alembic 002).
        dim = settings.embedding_dimensions
        for table, col in [("artifacts", "embedding"), ("claims", "embedding")]:
            row = await conn.execute(
                __import__("sqlalchemy").text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = :tbl AND column_name = :col"
                ),
                {"tbl": table, "col": col},
            )
            if row.first() is None:
                await conn.execute(
                    __import__("sqlalchemy").text(
                        f"ALTER TABLE {table} ADD COLUMN {col} vector({dim})"
                    )
                )
                _logger.info("Added %s.%s vector(%d) column", table, col, dim)


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
