"""InfoRequestService -- inter-agent request protocol with cycle detection.

Agents can request information from other agents. The service stores requests
in the DB (info_requests table) and provides query/response methods.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update

from backend.models.info_request import InfoRequest
from backend.types import AgentRole

logger = logging.getLogger(__name__)


class InfoRequestService:
    """Manages inter-agent information requests with chain cycle detection."""

    def __init__(self, session_factory, project_id: str) -> None:
        self._session_factory = session_factory
        self._project_id = uuid.UUID(project_id) if isinstance(project_id, str) else project_id

    async def create_request(
        self,
        requester: AgentRole,
        responder: AgentRole,
        question: str,
    ) -> str | None:
        """Create an inter-agent request. Returns request ID or None if cycle detected.

        Chain cycle detection: builds a graph of pending requests and checks if
        adding requester→responder would create a cycle of any length
        (e.g. A→B→C→A).
        """
        if requester == responder:
            logger.warning("[InfoRequest] Self-request rejected: %s", requester.value)
            return None

        async with self._session_factory() as session:
            # Load all pending requests as a directed graph
            stmt = select(InfoRequest).where(
                InfoRequest.project_id == self._project_id,
                InfoRequest.status == "pending",
            )
            result = await session.execute(stmt)
            pending_rows = result.scalars().all()

            # Build adjacency list: requester_role → set of responder_roles
            graph: dict[str, set[str]] = {}
            for r in pending_rows:
                graph.setdefault(r.requester_role, set()).add(r.responder_role)

            # Simulate adding the new edge and check for reachability
            # (responder can reach requester = cycle)
            graph.setdefault(requester.value, set()).add(responder.value)
            if self._has_cycle(graph, responder.value, requester.value):
                logger.warning(
                    "[InfoRequest] Chain cycle detected: %s→%s would form a cycle",
                    requester.value,
                    responder.value,
                )
                return None

            request_id = str(uuid.uuid4())
            req = InfoRequest(
                id=uuid.UUID(request_id),
                project_id=self._project_id,
                requester_role=requester.value,
                responder_role=responder.value,
                question=question,
                status="pending",
            )
            session.add(req)
            await session.commit()

            logger.info(
                "[InfoRequest] Created: %s→%s (%s) id=%s",
                requester.value,
                responder.value,
                question[:60],
                request_id[:8],
            )
            return request_id

    async def get_pending_for(self, role: AgentRole) -> list[dict]:
        """Get all pending requests where this role is the responder."""
        async with self._session_factory() as session:
            stmt = (
                select(InfoRequest)
                .where(
                    InfoRequest.project_id == self._project_id,
                    InfoRequest.responder_role == role.value,
                    InfoRequest.status == "pending",
                )
                .order_by(InfoRequest.created_at)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                {
                    "request_id": str(r.id),
                    "requester": r.requester_role,
                    "question": r.question,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ]

    async def get_pending_count_by_responder(self) -> dict[str, int]:
        """Get count of pending requests grouped by responder role."""
        async with self._session_factory() as session:
            stmt = select(InfoRequest).where(
                InfoRequest.project_id == self._project_id,
                InfoRequest.status == "pending",
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

        counts: dict[str, int] = {}
        for r in rows:
            role = r.responder_role or ""
            counts[role] = counts.get(role, 0) + 1
        return counts

    async def respond(self, request_id: str, response_text: str) -> None:
        """Mark a request as responded."""
        async with self._session_factory() as session:
            stmt = (
                update(InfoRequest)
                .where(InfoRequest.id == uuid.UUID(request_id))
                .values(
                    response=response_text,
                    status="responded",
                    responded_at=datetime.now(UTC),
                )
            )
            await session.execute(stmt)
            await session.commit()
            logger.info("[InfoRequest] Responded: %s", request_id[:8])

    @staticmethod
    def _has_cycle(graph: dict[str, set[str]], start: str, target: str) -> bool:
        """BFS from start to see if target is reachable (= cycle exists)."""
        visited: set[str] = set()
        queue = [start]
        while queue:
            node = queue.pop(0)
            if node == target:
                return True
            if node in visited:
                continue
            visited.add(node)
            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        return False
