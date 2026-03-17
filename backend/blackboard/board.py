"""Blackboard -- central shared workspace backed by the filesystem."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
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
        # Write-through caches (Blackboard is the sole writer, no TTL needed)
        self._artifact_cache: dict[str, list[ArtifactMeta]] = {}
        self._meta_cache: dict[str, Any] | None = None
        # version cache: "type/artifact_id" -> latest version int
        self._version_cache: dict[str, int] = {}
        # L0 content cache: "type/artifact_id/vN" -> L0 text (for get_state_summary)
        self._l0_cache: dict[str, str] = {}

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
            meta = {
                "created_at": datetime.now(UTC).isoformat(),
                "phase": "explore",
                "research_topic": research_topic,
            }
            await self._write_json(self._meta_path, meta)
            self._meta_cache = meta
        elif research_topic:
            # Ensure research_topic is persisted even on restart
            meta = await self.get_project_meta()
            if not meta.get("research_topic"):
                meta["research_topic"] = research_topic
                await self._write_json(self._meta_path, meta)
                self._meta_cache = meta
        # Initialize artifact cache
        self._artifact_cache = {}
        for at in ArtifactType:
            self._artifact_cache[at.value] = await self._list_artifacts_from_fs(at)

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

        # Update write-through caches
        cache_key = artifact_type.value
        cached = self._artifact_cache.get(cache_key, [])
        replaced = False
        for i, existing in enumerate(cached):
            if existing.artifact_id == artifact_id:
                cached[i] = meta
                replaced = True
                break
        if not replaced:
            cached.append(meta)
        self._artifact_cache[cache_key] = cached

        # Version cache
        ver_key = f"{cache_key}/{artifact_id}"
        self._version_cache[ver_key] = version

        if self._level_gen:
            try:
                l0 = await self._level_gen.generate_l0(content_l2, artifact_type)
                await self._write_text(ver_dir / "l0.txt", l0)
                # L0 content cache
                l0_key = f"{cache_key}/{artifact_id}/v{version}"
                self._l0_cache[l0_key] = l0
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
            l0_key = f"{artifact_type.value}/{artifact_id}/v{version}"
            if l0_key in self._l0_cache:
                return self._l0_cache[l0_key]
            text = await self._read_text(ver_dir / "l0.txt")
            if text is not None:
                self._l0_cache[l0_key] = text
            return text
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
        data["updated_at"] = datetime.now(UTC).isoformat()
        await self._write_json(path, data)
        # Sync cache
        cache_key = artifact_type.value
        if cache_key in self._artifact_cache:
            for i, m in enumerate(self._artifact_cache[cache_key]):
                if m.artifact_id == artifact_id:
                    self._artifact_cache[cache_key][i] = ArtifactMeta(**data)
                    break

    async def _list_artifacts_from_fs(
        self,
        artifact_type: ArtifactType,
    ) -> list[ArtifactMeta]:
        """Read all artifact metas from filesystem (for cache init / miss)."""
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
            results.append(ArtifactMeta(**data))
        return results

    async def list_artifacts(
        self,
        artifact_type: ArtifactType,
        include_superseded: bool = False,
    ) -> list[ArtifactMeta]:
        cache_key = artifact_type.value
        if cache_key not in self._artifact_cache:
            self._artifact_cache[cache_key] = await self._list_artifacts_from_fs(artifact_type)
        cached = self._artifact_cache[cache_key]
        if include_superseded:
            return list(cached)
        return [m for m in cached if not m.superseded]

    async def get_latest_version(self, artifact_type: ArtifactType, artifact_id: str) -> int:
        ver_key = f"{artifact_type.value}/{artifact_id}"
        if ver_key in self._version_cache:
            return self._version_cache[ver_key]
        base = self._artifact_dir(artifact_type, artifact_id)
        if not base.exists():
            return 0
        versions = [
            int(d.name[1:])
            for d in base.iterdir()
            if d.is_dir() and d.name.startswith("v") and d.name[1:].isdigit()
        ]
        result = max(versions) if versions else 0
        self._version_cache[ver_key] = result
        return result

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
        existing.resolved_at = datetime.now(UTC)
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
        if self._meta_cache is not None:
            return dict(self._meta_cache)
        data = await self._read_json(self._meta_path)
        self._meta_cache = data or {}
        return dict(self._meta_cache)

    async def update_project_meta(self, **kwargs: Any) -> None:
        meta = await self.get_project_meta()
        meta.update(kwargs)
        meta["updated_at"] = datetime.now(UTC).isoformat()
        await self._write_json(self._meta_path, meta)
        self._meta_cache = meta

    # ------------------------------------------------------------------
    # Board Protocol (required by OrchestrationEngine)
    # ------------------------------------------------------------------

    async def get_state_summary(
        self,
        level: ContextLevel = ContextLevel.L0,
        relevant_types: set[ArtifactType] | None = None,
    ) -> str:
        """Build a summary of non-superseded artifacts.

        Args:
            level: Context detail level (L0/L1/L2).
            relevant_types: If set, only include these artifact types.
                Research topic, phase/iteration, lane context, and open challenges
                are always included regardless of this filter.
        """
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

        # Inject lessons learned from previous projects (if available)
        lessons = meta.get("lessons_learned", "")
        if lessons:
            lines.append(f"\n## Lessons from Previous Research\n{lessons}\n")

        types_to_scan = relevant_types if relevant_types is not None else set(ArtifactType)
        for at in ArtifactType:
            if at not in types_to_scan:
                continue
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
        """Filter out duplicate write_artifact actions using text similarity."""
        from backend.types import ActionType

        result: list[BlackboardAction] = []
        for action in actions:
            if action.action_type != ActionType.WRITE_ARTIFACT:
                result.append(action)
                continue
            text = self._extract_action_text(action)
            if not text or len(text) < 30:
                result.append(action)
                continue
            art_type_str = action.content.get("artifact_type", action.target)
            try:
                art_type = ArtifactType(art_type_str)
            except ValueError:
                result.append(action)
                continue
            if await self._is_duplicate(art_type, text):
                logger.info(
                    "[Blackboard] Dedup: skipping duplicate %s artifact (%.40s...)",
                    art_type.value,
                    text,
                )
                continue
            result.append(action)
        return result

    @staticmethod
    def _extract_action_text(action: BlackboardAction) -> str:
        """Extract primary text content from action for dedup comparison."""
        c = action.content
        for key in ("text", "content", "hypothesis", "body", "section", "summary"):
            val = c.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        if isinstance(c.get("findings"), list):
            return " ".join(str(f) for f in c["findings"])
        return ""

    async def _is_duplicate(
        self,
        art_type: ArtifactType,
        new_text: str,
        threshold: float = 0.6,
    ) -> bool:
        """Check if new_text is too similar to any existing artifact of the same type."""
        existing = await self.list_artifacts(art_type)
        if not existing:
            return False
        new_words = set(new_text.lower().split())
        if len(new_words) < 5:
            return False
        for meta in existing[-10:]:
            ver = await self.get_latest_version(art_type, meta.artifact_id)
            if ver == 0:
                continue
            content = await self.read_artifact(art_type, meta.artifact_id, ver, ContextLevel.L2)
            if not content:
                continue
            existing_text = content if isinstance(content, str) else json.dumps(content)
            existing_words = set(existing_text.lower().split())
            if not existing_words:
                continue
            intersection = new_words & existing_words
            union = new_words | existing_words
            jaccard = len(intersection) / len(union) if union else 0
            if jaccard >= threshold:
                return True
        return False

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
        """Persist the critic score for a specific phase.

        Uses Exponential Moving Average (EMA) so recent scores are weighted
        more heavily, preventing early low scores from permanently dragging
        down the average.  alpha=0.4 means ~40% weight on the newest score.
        For the very first score, EMA simply equals that score.
        """
        ema_alpha = 0.4

        meta = await self.get_project_meta()
        phase_scores = meta.get("phase_critic_scores", {})
        phase_counts = meta.get("phase_critic_counts", {})
        old_ema = float(phase_scores.get(phase.value, 0.0))
        old_count = int(phase_counts.get(phase.value, 0))

        if old_count == 0:
            new_ema = score
        else:
            new_ema = ema_alpha * score + (1 - ema_alpha) * old_ema

        phase_scores[phase.value] = round(new_ema, 2)
        phase_counts[phase.value] = old_count + 1
        await self.update_project_meta(
            phase_critic_scores=phase_scores,
            phase_critic_counts=phase_counts,
        )
        logger.info(
            "[Board] Phase %s critic score: %.1f → EMA %.2f (α=%.1f, n=%d)",
            phase.value,
            score,
            new_ema,
            ema_alpha,
            old_count + 1,
        )

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
        keywords = ("contradict", "矛盾", "冲突", "不一致", "相悖", "反驳")
        challenges = await self.list_challenges()
        for ch in challenges:
            if ch.status == ChallengeStatus.OPEN:
                arg = ch.argument.lower()
                if any(kw in arg for kw in keywords):
                    return True
        return False

    async def has_logic_gaps(self) -> bool:
        keywords = ("gap", "logic", "漏洞", "逻辑", "缺失", "不完整", "推理")
        challenges = await self.list_challenges()
        for ch in challenges:
            if ch.status == ChallengeStatus.OPEN:
                arg = ch.argument.lower()
                if any(kw in arg for kw in keywords):
                    return True
        return False

    async def has_direction_issues(self) -> bool:
        keywords = ("direction", "方向", "偏离", "偏题", "跑偏", "离题")
        challenges = await self.list_challenges()
        for ch in challenges:
            if ch.status == ChallengeStatus.OPEN:
                arg = ch.argument.lower()
                if any(kw in arg for kw in keywords):
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
