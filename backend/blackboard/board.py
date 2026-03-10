"""Blackboard -- central shared workspace backed by the filesystem."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles

from backend.types import (
    ArtifactMeta,
    ArtifactType,
    BlackboardAction,
    ChallengeRecord,
    ChallengeStatus,
    ContextLevel,
    DecisionRecord,
    Message,
    ResearchPhase,
)

if TYPE_CHECKING:
    from backend.blackboard.actions import ActionExecutor
    from backend.blackboard.levels import LevelGenerator

logger = logging.getLogger(__name__)

_BOARD_DIRS = ("artifacts", "messages", "challenges", "decisions", "index", "scratch")


class Blackboard:
    def __init__(
        self,
        project_path: Path,
        level_generator: LevelGenerator | None = None,
        action_executor: ActionExecutor | None = None,
    ) -> None:
        self._root = project_path
        self._meta_path = self._root / "meta.json"
        self._level_gen = level_generator
        self._action_executor = action_executor

    @property
    def root(self) -> Path:
        return self._root

    def set_level_generator(self, gen: LevelGenerator) -> None:
        self._level_gen = gen

    # ------------------------------------------------------------------
    # Workspace lifecycle
    # ------------------------------------------------------------------

    async def init_workspace(self, research_topic: str = "") -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        for d in _BOARD_DIRS:
            (self._root / d).mkdir(parents=True, exist_ok=True)
        for at in ArtifactType:
            (self._root / "artifacts" / at.value).mkdir(parents=True, exist_ok=True)
        if not self._meta_path.exists():
            await self._write_json(
                self._meta_path,
                {
                    "created_at": datetime.utcnow().isoformat(),
                    "phase": "explore",
                    "research_topic": research_topic,
                },
            )
        elif research_topic:
            # Ensure research_topic is persisted even on restart
            meta = await self.get_project_meta()
            if not meta.get("research_topic"):
                meta["research_topic"] = research_topic
                await self._write_json(self._meta_path, meta)

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
                    artifact_type.value,
                    artifact_id,
                    version,
                    exc,
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

    async def get_latest_version(self, artifact_type: ArtifactType, artifact_id: str) -> int:
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

    async def resolve_challenge(
        self,
        challenge_id: str,
        resolution: str,
        status: ChallengeStatus = ChallengeStatus.DISMISSED,
    ) -> None:
        """Dismiss or resolve an open challenge by ID."""
        existing = await self.read_challenge(challenge_id)
        if existing is None:
            logger.warning("resolve_challenge: challenge %s not found", challenge_id)
            return
        existing.status = status
        existing.response = resolution
        existing.resolved_at = datetime.utcnow()
        await self.write_challenge(existing)

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
        return [c for c in await self.list_challenges() if c.status == ChallengeStatus.OPEN]

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
    # Board Protocol (required by OrchestrationEngine)
    # ------------------------------------------------------------------

    async def get_state_summary(self, level: ContextLevel = ContextLevel.L0) -> str:
        """Build a panoramic summary of all non-superseded artifacts."""
        lines: list[str] = []
        meta = await self.get_project_meta()
        phase = meta.get("phase", "explore")
        iteration = meta.get("iteration", 0)
        research_topic = meta.get("research_topic", "")

        # Always show research topic prominently at the top to prevent drift
        if research_topic:
            lines.append(
                f"## ⚠️ RESEARCH TOPIC — ALL WORK MUST STAY ON THIS TOPIC\n{research_topic}\n---"
            )

        lines.append(f"Phase: {phase} | Iteration: {iteration}")

        # Include cross-lane context for synthesis phase
        lane_context = meta.get("lane_context", "")
        if lane_context:
            lines.append(
                "\n## Cross-Lane Research Findings\n"
                "The following artifacts were produced by independent research lanes:\n"
                f"{lane_context[:40000]}"
            )

        for at in ArtifactType:
            metas = await self.list_artifacts(at)
            if not metas:
                continue
            lines.append(f"\n### {at.value} ({len(metas)} artifacts)")
            for m in metas:
                ver = await self.get_latest_version(at, m.artifact_id)
                if ver == 0:
                    continue
                content = await self.read_artifact(at, m.artifact_id, ver, level)
                if isinstance(content, str):
                    text = content
                elif content:
                    text = json.dumps(content, ensure_ascii=False)[:600]
                else:
                    text = "(empty)"
                lines.append(f"  - {m.artifact_id} v{ver}: {text[:500]}")

        open_ch = await self.get_open_challenges()
        if open_ch:
            lines.append(f"\n### Open Challenges ({len(open_ch)})")
            for ch in open_ch:
                lines.append(f"  - [{ch.challenger.value}] {ch.argument[:120]}")

        return "\n".join(lines)

    async def apply_action(self, action: BlackboardAction) -> None:
        if self._action_executor is None:
            from backend.blackboard.actions import ActionExecutor

            self._action_executor = ActionExecutor()
        await self._action_executor.execute(action, self)

    async def dedup_check(self, actions: list[BlackboardAction]) -> list[BlackboardAction]:
        """Pass through all actions (dedup requires embedding service, skip when unavailable)."""
        return actions

    async def get_open_challenge_count(self) -> int:
        return len(await self.get_open_challenges())

    async def get_latest_critic_score(self) -> float:
        reviews = await self.list_artifacts(ArtifactType.REVIEW)
        if not reviews:
            return 0.0
        latest = reviews[-1]
        ver = await self.get_latest_version(ArtifactType.REVIEW, latest.artifact_id)
        if ver == 0:
            return 0.0
        # Try L1 first (structured summary with overall_score key)
        l1 = await self.read_artifact(ArtifactType.REVIEW, latest.artifact_id, ver, ContextLevel.L1)
        if isinstance(l1, dict):
            score = l1.get("overall_score") or l1.get("score")
            if isinstance(score, (int, float)):
                return float(score)
        # Fall back to L2 raw content (critic writes {"score": N, ...})
        l2_raw = await self.read_artifact(
            ArtifactType.REVIEW, latest.artifact_id, ver, ContextLevel.L2
        )
        if isinstance(l2_raw, str):
            try:
                data = json.loads(l2_raw)
                score = data.get("score") or data.get("overall_score")
                if isinstance(score, (int, float)):
                    return float(score)
            except Exception:
                pass
        return 0.0

    async def get_phase_critic_score(self, phase: ResearchPhase) -> float:
        """Return the critic score recorded for this specific phase (0.0 if none)."""
        meta = await self.get_project_meta()
        phase_scores = meta.get("phase_critic_scores", {})
        return float(phase_scores.get(phase.value, 0.0))

    async def set_phase_critic_score(self, phase: ResearchPhase, score: float) -> None:
        """Persist the critic score for a specific phase."""
        meta = await self.get_project_meta()
        phase_scores = meta.get("phase_critic_scores", {})
        phase_scores[phase.value] = score
        await self.update_project_meta(phase_critic_scores=phase_scores)

    async def get_recent_revision_count(self, rounds: int) -> int:
        """Count artifacts that have version > 1 (indicating revisions)."""
        count = 0
        for at in ArtifactType:
            metas = await self.list_artifacts(at)
            for m in metas:
                if m.version > 1:
                    count += 1
        return count

    async def get_phase_iteration_count(self, phase: ResearchPhase) -> int:
        meta = await self.get_project_meta()
        phase_iters = meta.get("phase_iterations", {})
        return phase_iters.get(phase.value, 0)

    async def increment_phase_iteration(self, phase: ResearchPhase) -> int:
        meta = await self.get_project_meta()
        phase_iters = meta.get("phase_iterations", {})
        new_val = phase_iters.get(phase.value, 0) + 1
        phase_iters[phase.value] = new_val
        await self.update_project_meta(phase_iterations=phase_iters)
        return new_val

    async def get_artifacts_since_phase(self, phase: ResearchPhase) -> list[str]:
        """List artifact IDs from the current or given phase."""
        result: list[str] = []
        for at in ArtifactType:
            metas = await self.list_artifacts(at)
            for m in metas:
                result.append(f"{at.value}/{m.artifact_id}")
        return result

    async def mark_superseded(self, artifact_id: str) -> None:
        for at in ArtifactType:
            meta = await self.read_artifact_meta(at, artifact_id)
            if meta is not None:
                await self.update_artifact_meta(at, artifact_id, superseded=True)
                return

    async def update_meta(self, key: str, value: object) -> None:
        await self.update_project_meta(**{key: value})

    async def has_contradictory_evidence(self) -> bool:
        challenges = await self.list_challenges()
        for ch in challenges:
            if ch.status == ChallengeStatus.OPEN and "contradict" in ch.argument.lower():
                return True
        return False

    async def has_logic_gaps(self) -> bool:
        challenges = await self.list_challenges()
        for ch in challenges:
            if ch.status == ChallengeStatus.OPEN and (
                "gap" in ch.argument.lower() or "logic" in ch.argument.lower()
            ):
                return True
        return False

    async def has_direction_issues(self) -> bool:
        challenges = await self.list_challenges()
        for ch in challenges:
            if ch.status == ChallengeStatus.OPEN and "direction" in ch.argument.lower():
                return True
        return False

    async def serialize(self) -> dict[str, Any]:
        meta = await self.get_project_meta()
        artifacts: dict[str, list[dict[str, Any]]] = {}
        for at in ArtifactType:
            metas = await self.list_artifacts(at, include_superseded=True)
            if metas:
                artifacts[at.value] = [m.model_dump(mode="json") for m in metas]
        challenges = [c.model_dump(mode="json") for c in await self.list_challenges()]
        decisions = [d.model_dump(mode="json") for d in await self.get_decisions()]
        messages = [m.model_dump(mode="json") for m in await self.get_messages()]
        return {
            "meta": meta,
            "artifacts": artifacts,
            "challenges": challenges,
            "decisions": decisions,
            "messages": messages,
        }

    async def export_paper(self) -> Path | None:
        """Collect ALL non-superseded DRAFT artifacts, order by section,
        and write a combined paper to exports/paper.md.

        If DRAFT artifacts are sparse, supplement with HYPOTHESES and
        EVIDENCE_FINDINGS to produce a more complete export.
        """
        metas = await self.list_artifacts(ArtifactType.DRAFT)

        section_order = [
            "title",
            "abstract",
            "摘要",
            "标题",
            "introduction",
            "引言",
            "background",
            "背景",
            "hypothesis",
            "假设",
            "method",
            "方法",
            "evidence",
            "证据",
            "result",
            "结果",
            "discussion",
            "讨论",
            "conclusion",
            "结论",
            "reference",
            "参考",
        ]

        def _section_sort_key(section_name: str) -> int:
            lower = section_name.lower()
            for i, keyword in enumerate(section_order):
                if keyword in lower:
                    return i
            return len(section_order)

        seen_sections: dict[str, str] = {}
        for m in metas:
            ver = await self.get_latest_version(ArtifactType.DRAFT, m.artifact_id)
            if ver == 0:
                continue
            raw = await self.read_artifact(
                ArtifactType.DRAFT,
                m.artifact_id,
                ver,
                ContextLevel.L2,
            )
            if not raw:
                continue
            text = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
            section_name = ""
            try:
                parsed = json.loads(text) if isinstance(text, str) else text
                if isinstance(parsed, dict):
                    section_name = parsed.get("section", "")
                    text = parsed.get("text", text)
            except (json.JSONDecodeError, TypeError):
                pass
            section_key = section_name or m.artifact_id
            seen_sections[section_key] = text

        # Supplement with other artifact types if drafts are sparse
        supplement_types = [
            (ArtifactType.HYPOTHESES, "hypotheses"),
            (ArtifactType.EVIDENCE_FINDINGS, "evidence"),
            (ArtifactType.DIRECTIONS, "directions"),
            (ArtifactType.OUTLINE, "outline"),
        ]
        for art_type, label in supplement_types:
            art_metas = await self.list_artifacts(art_type)
            for m in art_metas:
                ver = await self.get_latest_version(art_type, m.artifact_id)
                if ver == 0:
                    continue
                raw = await self.read_artifact(
                    art_type,
                    m.artifact_id,
                    ver,
                    ContextLevel.L2,
                )
                if not raw:
                    continue
                text = (
                    raw
                    if isinstance(raw, str)
                    else json.dumps(
                        raw,
                        ensure_ascii=False,
                    )
                )
                section_key = f"{label}_{m.artifact_id}"
                if section_key not in seen_sections:
                    seen_sections[section_key] = text

        if not seen_sections:
            logger.info("export_paper: no artifacts found for export")
            return None

        sorted_sections = sorted(
            seen_sections.items(),
            key=lambda kv: _section_sort_key(kv[0]),
        )
        combined = "\n\n---\n\n".join(text for _, text in sorted_sections)

        exports_dir = self._root / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        paper_path = exports_dir / "paper.md"
        await self._write_text(paper_path, combined)
        logger.info(
            "export_paper: written %d sections to %s",
            len(sorted_sections),
            paper_path,
        )
        return paper_path

    def get_project_path(self) -> Path:
        return self._root

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
            async with aiofiles.open(path, encoding="utf-8") as f:
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
            async with aiofiles.open(path, encoding="utf-8") as f:
                return await f.read()
        except OSError as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return None
