"""Heartbeat monitor for health checking and crash recovery."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Protocol

from backend.config import settings

logger = logging.getLogger(__name__)


class Board(Protocol):
    async def serialize(self) -> dict[str, Any]: ...
    def get_project_path(self) -> Path: ...


class HeartbeatMonitor:
    """Runs a periodic background task that snapshots blackboard state to
    ``meta.json`` and detects operational anomalies (agent timeout,
    consecutive failures, stale state).
    """

    def __init__(self, interval: int | None = None) -> None:
        self._interval = interval or settings.heartbeat_interval_seconds
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._last_activity: dict[str, datetime] = {}
        self._agent_statuses: dict[str, str] = {}
        self._consecutive_failures: dict[str, int] = {}
        self._ws_connected: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, project_id: str, board: Board) -> None:
        if project_id in self._tasks:
            logger.warning(
                "Heartbeat already running for project %s", project_id
            )
            return
        self._last_activity[project_id] = datetime.utcnow()
        self._consecutive_failures[project_id] = 0
        task = asyncio.create_task(self._loop(project_id, board))
        self._tasks[project_id] = task
        logger.info("Heartbeat started for project %s", project_id)

    async def stop(self, project_id: str) -> None:
        task = self._tasks.pop(project_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._last_activity.pop(project_id, None)
        self._consecutive_failures.pop(project_id, None)
        logger.info("Heartbeat stopped for project %s", project_id)

    # ------------------------------------------------------------------
    # Health API
    # ------------------------------------------------------------------

    def check_health(self) -> dict[str, Any]:
        return {
            "agent_statuses": dict(self._agent_statuses),
            "ws_connected": self._ws_connected,
            "last_activity": {
                k: v.isoformat() for k, v in self._last_activity.items()
            },
            "consecutive_failures": dict(self._consecutive_failures),
            "active_projects": list(self._tasks.keys()),
        }

    def record_activity(self, project_id: str) -> None:
        self._last_activity[project_id] = datetime.utcnow()
        self._consecutive_failures[project_id] = 0

    def record_agent_status(self, role: str, status: str) -> None:
        self._agent_statuses[role] = status

    def record_failure(self, project_id: str) -> None:
        self._consecutive_failures[project_id] = (
            self._consecutive_failures.get(project_id, 0) + 1
        )

    def set_ws_connected(self, connected: bool) -> None:
        self._ws_connected = connected

    # ------------------------------------------------------------------
    # Snapshot / recovery
    # ------------------------------------------------------------------

    async def snapshot_state(self, board: Board) -> None:
        project_path = board.get_project_path()
        state = await board.serialize()
        # 使用独立文件，避免与 board 的 meta.json 冲突
        snapshot_path = project_path / "snapshot.json"
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(
            json.dumps(
                {
                    "snapshot_at": datetime.utcnow().isoformat(),
                    "state": state,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        logger.debug("State snapshot saved to %s", snapshot_path)

    @staticmethod
    def recover_from_snapshot(
        project_path: Path,
    ) -> Optional[dict[str, Any]]:
        snapshot_path = project_path / "snapshot.json"
        if not snapshot_path.exists():
            logger.warning("No snapshot found at %s", snapshot_path)
            return None
        try:
            data = json.loads(snapshot_path.read_text())
            logger.info(
                "Recovered snapshot from %s",
                data.get("snapshot_at", "unknown"),
            )
            return data.get("state")  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to recover snapshot: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _loop(self, project_id: str, board: Board) -> None:
        while True:
            await asyncio.sleep(self._interval)
            try:
                await self.snapshot_state(board)
                self._detect_issues(project_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Heartbeat loop error for %s", project_id
                )

    def _detect_issues(self, project_id: str) -> None:
        last = self._last_activity.get(project_id)
        if last:
            elapsed = (datetime.utcnow() - last).total_seconds()
            if elapsed > self._interval * 3:
                logger.warning(
                    "Stale state for %s: no activity for %.0fs",
                    project_id,
                    elapsed,
                )

        failures = self._consecutive_failures.get(project_id, 0)
        if failures >= 3:
            logger.warning(
                "Project %s has %d consecutive failures",
                project_id,
                failures,
            )
