"""Unit tests for InfoRequestService.

Uses the project's PostgreSQL database (running in Docker).
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import settings
from backend.models import Base
from backend.models.project import Project
from backend.orchestrator.info_request_service import InfoRequestService
from backend.types import AgentRole


@pytest_asyncio.fixture
async def db_session_factory():
    """Connect to the running PostgreSQL and ensure tables exist."""
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def project_id(db_session_factory):
    """Create a real project in the DB and return its ID."""
    pid = str(uuid.uuid4())
    async with db_session_factory() as session:
        project = Project(
            id=pid,
            name="test-info-request",
            research_topic="test topic",
        )
        session.add(project)
        await session.commit()
    return pid


class TestInfoRequestService:
    @pytest.mark.asyncio
    async def test_create_and_get_pending(self, db_session_factory, project_id):
        svc = InfoRequestService(db_session_factory, project_id)

        req_id = await svc.create_request(
            AgentRole.CRITIC, AgentRole.SCIENTIST, "What evidence supports H1?"
        )
        assert req_id is not None

        pending = await svc.get_pending_for(AgentRole.SCIENTIST)
        assert len(pending) == 1
        assert pending[0]["requester"] == "critic"
        assert "H1" in pending[0]["question"]

    @pytest.mark.asyncio
    async def test_self_request_rejected(self, db_session_factory, project_id):
        svc = InfoRequestService(db_session_factory, project_id)
        result = await svc.create_request(
            AgentRole.CRITIC, AgentRole.CRITIC, "Self-question"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_cycle_detection(self, db_session_factory, project_id):
        svc = InfoRequestService(db_session_factory, project_id)

        # A→B is fine
        req1 = await svc.create_request(
            AgentRole.CRITIC, AgentRole.SCIENTIST, "Question 1"
        )
        assert req1 is not None

        # B→A would form a cycle (A→B already pending)
        req2 = await svc.create_request(
            AgentRole.SCIENTIST, AgentRole.CRITIC, "Question 2"
        )
        assert req2 is None

    @pytest.mark.asyncio
    async def test_respond_clears_pending(self, db_session_factory, project_id):
        svc = InfoRequestService(db_session_factory, project_id)

        req_id = await svc.create_request(
            AgentRole.CRITIC, AgentRole.LIBRARIAN, "Find more evidence"
        )
        assert req_id is not None

        await svc.respond(req_id, "Found 3 papers")

        # Should no longer appear in pending
        pending = await svc.get_pending_for(AgentRole.LIBRARIAN)
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_get_pending_count_by_responder(
        self, db_session_factory, project_id
    ):
        svc = InfoRequestService(db_session_factory, project_id)

        await svc.create_request(AgentRole.CRITIC, AgentRole.SCIENTIST, "Q1")
        await svc.create_request(AgentRole.DIRECTOR, AgentRole.SCIENTIST, "Q2")
        await svc.create_request(AgentRole.CRITIC, AgentRole.LIBRARIAN, "Q3")

        counts = await svc.get_pending_count_by_responder()
        assert counts.get("scientist", 0) == 2
        assert counts.get("librarian", 0) == 1

    @pytest.mark.asyncio
    async def test_cycle_allowed_after_response(
        self, db_session_factory, project_id
    ):
        svc = InfoRequestService(db_session_factory, project_id)

        # A→B
        req_id = await svc.create_request(
            AgentRole.CRITIC, AgentRole.SCIENTIST, "Q1"
        )
        # Respond to A→B
        await svc.respond(req_id, "Answer")

        # Now B→A should be allowed (no pending A→B)
        req2 = await svc.create_request(
            AgentRole.SCIENTIST, AgentRole.CRITIC, "Q2"
        )
        assert req2 is not None

    @pytest.mark.asyncio
    async def test_chain_cycle_detection(self, db_session_factory, project_id):
        """A→B→C→A should be detected as a 3-step cycle."""
        svc = InfoRequestService(db_session_factory, project_id)

        # A→B: fine
        req1 = await svc.create_request(
            AgentRole.CRITIC, AgentRole.SCIENTIST, "Q1"
        )
        assert req1 is not None

        # B→C: fine
        req2 = await svc.create_request(
            AgentRole.SCIENTIST, AgentRole.LIBRARIAN, "Q2"
        )
        assert req2 is not None

        # C→A: would form cycle A→B→C→A
        req3 = await svc.create_request(
            AgentRole.LIBRARIAN, AgentRole.CRITIC, "Q3"
        )
        assert req3 is None

    @pytest.mark.asyncio
    async def test_different_projects_isolated(self, db_session_factory):
        pid1 = str(uuid.uuid4())
        pid2 = str(uuid.uuid4())
        # Create both projects in DB to satisfy FK constraint (one at a time)
        async with db_session_factory() as session:
            session.add(Project(id=pid1, name="p1", research_topic="t1"))
            await session.commit()
        async with db_session_factory() as session:
            session.add(Project(id=pid2, name="p2", research_topic="t2"))
            await session.commit()

        svc1 = InfoRequestService(db_session_factory, pid1)
        svc2 = InfoRequestService(db_session_factory, pid2)

        await svc1.create_request(AgentRole.CRITIC, AgentRole.SCIENTIST, "Q1")

        # Project 2 should see no pending requests
        pending = await svc2.get_pending_for(AgentRole.SCIENTIST)
        assert len(pending) == 0
