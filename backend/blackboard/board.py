"""Blackboard -- central shared workspace backed by the filesystem."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

import aiofiles

from backend.types import (
    ArtifactMeta,
    ArtifactType,
    ChallengeRecord,
    ChallengeStatus,
    ContextLevel,
    DecisionRecord,
    Message,
)

if TYPE_CHECKING:
    from backend.blackboard.levels import LevelGenerator

logger = logging.getLogger(__name__)

_BOARD_DIRS = ("artifacts", "messages", "challenges", "decisions", "index", "scratch")


class Blackboard:

    def __init__(
        self,
        project_path: Path,
        level_generator: LevelGenerator | None = None,
    ) -> None:
        self._root = project_path
        self._meta_path = self._root / "meta.json"
        self._level_gen = level_generator

    @property
    def root(self) -> Path:
        return self._root

    def set_level_generator(self, gen: LevelGenerator) -> None:
        self._level_gen = gen

    # ------------------------------------------------------------------
    # Workspace lifecycle
    # ------------------------------------------------------------------

    async def init_workspace(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        for d in _BOARD_DIRS:
            (self._root / d).mkdir(parents=True, exist_ok=True)
        for at in ArtifactType:
            (self._root / "artifacts" / at.value).mkdir(parents=True, exist_ok=True)
        if not self._meta_path.exists():
            await self._write_json(self._meta_path, {
                "created_at": datetime.utcnow().isoformat(),
                "phase": "explore",
            })

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    async def write_artifact(
        self,
        artifact_type: ArtifactType,
        artifact_id: str,
        version: int,
        content_l2: str,
        meta: ArtifactMeta,
    ) -> None:
        base = self._artifact_dir(artifact_type, artifact_id)
        ver_dir = base / f"v{version}"
        ver_dir.mkdir(parents=True, exist_ok=True)

        await self._write_text(ver_dir / "l2.json", content_l2)
        await self._write_json(base / "meta.json", meta.model_dump(mode="json"))

        if self._level_gen:
            try:
                l0 = await self._level_gen.generate_l0(content_l2, artifact_type)
                await self._write_text(ver_dir / "l0.txt", l0)
                l1 = await self._level_gen.generate_l1(content_l2, artifact_type)
                await self._write_json(ver_dir / "l1.json", l1)
            except Exception as exc:
                logger.warning(
                    "Level generation failed for %s/%s v%d: %s",
                    artifact_type.value, artifact_id, version, exc,
                )

    async def write_artifact_level(
        self,
        artifact_type: ArtifactType,
        artifact_id: str,
        version: int,
        level: ContextLevel,
        content: str | dict,
    ) -> None:
        ver_dir = self._artifact_dir(artifact_type, artifact_id) / f"v{version}"
        ver_dir.mkdir(parents=True, exist_ok=True)
        if level == ContextLevel.L0:
            text = content if isinstance(content, str) else json.dumps(content)
            await self._write_text(ver_dir / "l0.txt", text)
        elif level == ContextLevel.L1:
            data = content if isinstance(content, dict) else {"summary": content}
            await self._write_json(ver_dir / "l1.json", data)
        else:
            text = content if isinstance(content, str) else json.dumps(content)
            await self._write_text(ver_dir / "l2.json", text)

    async def read_artifact(
        self,
        artifact_type: ArtifactType,
        artifact_id: str,
        version: int,
        level: ContextLevel = ContextLevel.L2,
    ) -> str | dict | None:
        ver_dir = self._artifact_dir(artifact_type, artifact_id) / f"v{version}"
        if level == ContextLevel.L0:
            return await self._read_text(ver_dir / "l0.txt")
        if level == ContextLevel.L1:
            return await self._read_json(ver_dir / "l1.json")
        return await self._read_text(ver_dir / "l2.json")

    async def read_artifact_meta(
        self,
        artifact_type: ArtifactType,
        artifact_id: str,
    ) -> ArtifactMeta | None:
        path = self._artifact_dir(artifact_type, artifact_id) / "meta.json"
        data = await self._read_json(path)
        if data is None:
            return None
        return ArtifactMeta(**data)

    async def update_artifact_meta(
        self,
        artifact_type: ArtifactType,
        artifact_id: str,
        **kwargs: Any,
    ) -> None:
        path = self._artifact_dir(artifact_type, artifact_id) / "meta.json"
        data = await self._read_json(path)
        if data is None:
            return
        data.update(kwargs)
        data["updated_at"] = datetime.utcnow().isoformat()
        await self._write_json(path, data)

    async def list_artifacts(
        self,
        artifact_type: ArtifactType,
        include_superseded: bool = False,
    ) -> list[ArtifactMeta]:
        type_dir = self._root / "artifacts" / artifact_type.value
        if not type_dir.exists():
            return []
        results: list[ArtifactMeta] = []
        for child in sorted(type_dir.iterdir()):
            if not child.is_dir():
                continue
            meta_path = child / "meta.json"
            if not meta_path.exists():
                continue
            data = await self._read_json(meta_path)
            if data is None:
                continue
            meta = ArtifactMeta(**data)
            if not include_superseded and meta.superseded:
                continue
            results.append(meta)
        return results

    async def get_latest_version(
        self, artifact_type: ArtifactType, artifact_id: str
    ) -> int:
        base = self._artifact_dir(artifact_type, artifact_id)
        if not base.exists():
            return 0
        versions = [
            int(d.name[1:])
            for d in base.iterdir()
            if d.is_dir() and d.name.startswith("v") and d.name[1:].isdigit()
        ]
        return max(versions) if versions else 0

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    async def post_message(self, message: Message) -> None:
        msg_dir = self._root / "messages"
        msg_dir.mkdir(parents=True, exist_ok=True)
        await self._write_json(
            msg_dir / f"{message.message_id}.json",
            message.model_dump(mode="json"),
        )

    async def get_messages(
        self,
        to_agent: str | None = None,
        since: datetime | None = None,
    ) -> list[Message]:
        msg_dir = self._root / "messages"
        if not msg_dir.exists():
            return []
        results: list[Message] = []
        for f in sorted(msg_dir.glob("*.json")):
            data = await self._read_json(f)
            if data is None:
                continue
            msg = Message(**data)
            if to_agent and msg.to_agent and msg.to_agent.value != to_agent:
                continue
            if since and msg.created_at < since:
                continue
            results.append(msg)
        return results

    # ------------------------------------------------------------------
    # Challenges
    # ------------------------------------------------------------------

    async def write_challenge(self, challenge: ChallengeRecord) -> None:
        ch_dir = self._root / "challenges"
        ch_dir.mkdir(parents=True, exist_ok=True)
        await self._write_json(
            ch_dir / f"{challenge.challenge_id}.json",
            challenge.model_dump(mode="json"),
        )

    async def read_challenge(self, challenge_id: str) -> ChallengeRecord | None:
        path = self._root / "challenges" / f"{challenge_id}.json"
        data = await self._read_json(path)
        if data is None:
            return None
        return ChallengeRecord(**data)

    async def list_challenges(self) -> list[ChallengeRecord]:
        ch_dir = self._root / "challenges"
        if not ch_dir.exists():
            return []
        results: list[ChallengeRecord] = []
        for f in sorted(ch_dir.glob("*.json")):
            data = await self._read_json(f)
            if data is None:
                continue
            results.append(ChallengeRecord(**data))
        return results

    async def get_open_challenges(self) -> list[ChallengeRecord]:
        return [
            c for c in await self.list_challenges()
            if c.status == ChallengeStatus.OPEN
        ]

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    async def write_decision(self, decision: DecisionRecord) -> None:
        dec_dir = self._root / "decisions"
        dec_dir.mkdir(parents=True, exist_ok=True)
        await self._write_json(
            dec_dir / f"{decision.decision_id}.json",
            decision.model_dump(mode="json"),
        )

    async def get_decisions(self, phase: str | None = None) -> list[DecisionRecord]:
        dec_dir = self._root / "decisions"
        if not dec_dir.exists():
            return []
        results: list[DecisionRecord] = []
        for f in sorted(dec_dir.glob("*.json")):
            data = await self._read_json(f)
            if data is None:
                continue
            rec = DecisionRecord(**data)
            if phase and rec.phase.value != phase:
                continue
            results.append(rec)
        return results

    # ------------------------------------------------------------------
    # Project meta
    # ------------------------------------------------------------------

    async def get_project_meta(self) -> dict[str, Any]:
        data = await self._read_json(self._meta_path)
        return data or {}

    async def update_project_meta(self, **kwargs: Any) -> None:
        meta = await self.get_project_meta()
        meta.update(kwargs)
        meta["updated_at"] = datetime.utcnow().isoformat()
        await self._write_json(self._meta_path, meta)

    # ------------------------------------------------------------------
    # Internal I/O
    # ------------------------------------------------------------------

    def _artifact_dir(self, artifact_type: ArtifactType, artifact_id: str) -> Path:
        return self._root / "artifacts" / artifact_type.value / artifact_id

    async def _write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, default=str, ensure_ascii=False, indent=2))

    async def _read_json(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                return json.loads(await f.read())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return None

    async def _write_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(text)

    async def _read_text(self, path: Path) -> str | None:
        if not path.exists():
            return None
        try:
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                return await f.read()
        except OSError as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return None
