"""SemanticBoard -- PostgreSQL + pgvector backed blackboard with semantic search."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, text

from backend.blackboard.board import Blackboard
from backend.blackboard.event_bus import ArtifactEvent, EventBus
from backend.config import settings
from backend.models.artifact import Artifact, ArtifactRelation
from backend.models.evaluation import KnowledgeState
from backend.types import AgentRole, ArtifactMeta, ArtifactType
from backend.utils.json_utils import safe_json_loads

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from backend.agents.base import LLMRouter
    from backend.blackboard.actions import ActionExecutor
    from backend.blackboard.levels import LevelGenerator
    from backend.knowledge.embeddings import EmbeddingService

logger = logging.getLogger(__name__)

# Semaphore to limit concurrent embedding API calls
_EMBED_SEMAPHORE = asyncio.Semaphore(5)

# Role -> artifact types affinity mapping
_ROLE_PRIMARY: dict[AgentRole, set[ArtifactType]] = {
    AgentRole.DIRECTOR: {ArtifactType.DIRECTIONS},
    AgentRole.SCIENTIST: {ArtifactType.HYPOTHESES, ArtifactType.EVIDENCE_GAPS,
                          ArtifactType.EXPERIMENT_GUIDE, ArtifactType.TREND_SIGNALS},
    AgentRole.LIBRARIAN: {ArtifactType.EVIDENCE_FINDINGS},
    AgentRole.WRITER: {ArtifactType.OUTLINE, ArtifactType.DRAFT},
    AgentRole.CRITIC: {ArtifactType.REVIEW},
    AgentRole.SYNTHESIZER: {ArtifactType.DRAFT},
}

_ROLE_DEPENDENCY: dict[AgentRole, set[ArtifactType]] = {
    AgentRole.DIRECTOR: {ArtifactType.EVIDENCE_FINDINGS, ArtifactType.REVIEW,
                         ArtifactType.TREND_SIGNALS},
    AgentRole.SCIENTIST: {ArtifactType.EVIDENCE_FINDINGS, ArtifactType.DIRECTIONS,
                          ArtifactType.REVIEW},
    AgentRole.LIBRARIAN: {ArtifactType.DIRECTIONS, ArtifactType.HYPOTHESES},
    AgentRole.WRITER: {ArtifactType.HYPOTHESES, ArtifactType.EVIDENCE_FINDINGS,
                       ArtifactType.DIRECTIONS, ArtifactType.REVIEW},
    AgentRole.CRITIC: {ArtifactType.HYPOTHESES, ArtifactType.EVIDENCE_FINDINGS,
                       ArtifactType.DRAFT, ArtifactType.OUTLINE},
    AgentRole.SYNTHESIZER: {ArtifactType.HYPOTHESES, ArtifactType.EVIDENCE_FINDINGS,
                            ArtifactType.REVIEW, ArtifactType.DIRECTIONS},
}


class SemanticBoard(Blackboard):
    """Extends Blackboard with PostgreSQL + pgvector storage and semantic search."""

    def __init__(
        self,
        project_path: Path,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_service: EmbeddingService | None,
        llm_router: LLMRouter,
        project_id: str,
        event_bus: EventBus,
        level_generator: LevelGenerator | None = None,
        action_executor: ActionExecutor | None = None,
    ) -> None:
        super().__init__(project_path, level_generator=level_generator,
                         action_executor=action_executor)
        self._session_factory = session_factory
        self._embedding_service = embedding_service
        self._llm_router = llm_router
        self._project_id = project_id
        self._event_bus = event_bus
        self._relation_extractor = None  # lazy init
        self._subtopic_cache: list[str] | None = None

    def _get_relation_extractor(self):
        if self._relation_extractor is None:
            from backend.blackboard.relation_extractor import RelationExtractor
            self._relation_extractor = RelationExtractor(
                self._session_factory, self._llm_router
            )
        return self._relation_extractor

    # ------------------------------------------------------------------
    # Overridden: write_artifact (dual-write)
    # ------------------------------------------------------------------

    async def write_artifact(
        self,
        artifact_type: ArtifactType,
        artifact_id: str,
        version: int,
        content_l2: str,
        meta: ArtifactMeta,
    ) -> None:
        # 1. Filesystem write (existing behavior)
        await super().write_artifact(artifact_type, artifact_id, version, content_l2, meta)

        # 2. Persist to PostgreSQL
        db_id = await self._persist_to_db(artifact_type, artifact_id, version, content_l2, meta)

        # 3. Fire-and-forget async post-write (embed + extract relations)
        if db_id is not None:
            asyncio.create_task(self._async_post_write(db_id, content_l2, artifact_type))

        # 4. Publish event
        await self._event_bus.publish(ArtifactEvent(
            event_type="created" if version == 1 else "updated",
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            agent_role=AgentRole(meta.created_by) if meta.created_by else AgentRole.DIRECTOR,
            project_id=self._project_id,
        ))

    # ------------------------------------------------------------------
    # Overridden: dedup_check (cosine similarity)
    # ------------------------------------------------------------------

    async def dedup_check(self, actions: list) -> list:
        if not self._embedding_service:
            return await super().dedup_check(actions)

        from backend.types import ActionType
        result = []
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
            if await self._semantic_is_duplicate(art_type, text):
                logger.info(
                    "[SemanticBoard] Semantic dedup: skipping duplicate %s (%.40s...)",
                    art_type.value, text,
                )
                continue
            result.append(action)
        return result

    async def _semantic_is_duplicate(
        self,
        art_type: ArtifactType,
        new_text: str,
    ) -> bool:
        threshold = settings.semantic_dedup_threshold
        try:
            async with _EMBED_SEMAPHORE:
                vec = await self._embedding_service.embed_text(new_text[:2000])
        except Exception:
            logger.warning("[SemanticBoard] Embedding failed for dedup, falling back to Jaccard")
            return await self._is_duplicate(art_type, new_text)

        try:
            async with self._session_factory() as session:
                # cosine distance < (1 - threshold) means similarity > threshold
                max_dist = 1.0 - threshold
                query = text(
                    "SELECT 1 FROM artifacts "
                    "WHERE project_id = :pid AND artifact_type = :atype "
                    "AND superseded = false AND embedding IS NOT NULL "
                    "AND embedding <=> CAST(:vec AS vector) < :max_dist "
                    "LIMIT 1"
                )
                row = (await session.execute(
                    query,
                    {
                        "pid": self._project_id,
                        "atype": art_type.value,
                        "vec": str(vec),
                        "max_dist": max_dist,
                    },
                )).first()
                return row is not None
        except Exception:
            logger.warning("[SemanticBoard] DB dedup query failed, falling back to Jaccard")
            return await self._is_duplicate(art_type, new_text)

    # ------------------------------------------------------------------
    # New: semantic search
    # ------------------------------------------------------------------

    async def find_relevant_artifacts(
        self,
        query: str,
        top_k: int = 20,
        artifact_types: list[ArtifactType] | None = None,
    ) -> list[tuple[uuid.UUID, str, str, float]]:
        """Find artifacts most similar to query via pgvector.

        Returns list of (db_id, artifact_type, artifact_id, cosine_similarity).
        """
        if not self._embedding_service:
            return []

        try:
            async with _EMBED_SEMAPHORE:
                query_vec = await self._embedding_service.embed_text(query[:2000])
        except Exception:
            logger.warning("[SemanticBoard] Embedding failed for search")
            return []

        try:
            type_filter = ""
            params: dict[str, Any] = {
                "pid": self._project_id,
                "vec": str(query_vec),
                "limit": top_k,
            }
            if artifact_types:
                placeholders = ", ".join(f":t{i}" for i in range(len(artifact_types)))
                type_filter = f"AND artifact_type IN ({placeholders})"
                for i, at in enumerate(artifact_types):
                    params[f"t{i}"] = at.value

            sql = text(
                f"SELECT id, artifact_type, artifact_id, "
                f"1.0 - (embedding <=> CAST(:vec AS vector)) AS similarity "
                f"FROM artifacts "
                f"WHERE project_id = :pid AND superseded = false "
                f"AND embedding IS NOT NULL {type_filter} "
                f"ORDER BY embedding <=> CAST(:vec AS vector) "
                f"LIMIT :limit"
            )
            async with self._session_factory() as session:
                rows = (await session.execute(sql, params)).fetchall()
                return [
                    (row[0], row[1], row[2], float(row[3]))
                    for row in rows
                ]
        except Exception:
            logger.warning("[SemanticBoard] Semantic search query failed", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # New: build_agent_context (semantic relevance-ranked)
    # ------------------------------------------------------------------

    async def build_agent_context(
        self,
        role: AgentRole,
        task_description: str,
        budget: int | None = None,
    ) -> str:
        """Build context for an agent using semantic relevance ranking.

        Scoring: 0.50 * cosine_sim + 0.20 * role_affinity + 0.15 * recency + 0.15 * centrality
        """
        budget = budget or settings.context_budget_tokens

        # Header: always included
        meta = await self.get_project_meta()
        research_topic = meta.get("research_topic", "")
        phase = meta.get("phase", "explore")
        iteration = meta.get("iteration", 0)

        header_lines = []
        if research_topic:
            header_lines.append(
                f"## RESEARCH TOPIC\n{research_topic}\n---"
            )
        header_lines.append(f"Phase: {phase} | Iteration: {iteration}")

        # Open challenges
        open_ch = await self.get_open_challenges()
        if open_ch:
            header_lines.append(f"\n### Open Challenges ({len(open_ch)})")
            for ch in open_ch[:5]:
                header_lines.append(f"  - [{ch.challenger.value}] {ch.argument[:120]}")

        header = "\n".join(header_lines)

        # Find relevant artifacts
        candidates = await self.find_relevant_artifacts(task_description, top_k=40)
        if not candidates:
            # Fallback to filesystem-based context
            from backend.blackboard.context_builder import build_budget_context
            return await build_budget_context(self, budget=budget)

        # Score each candidate
        now = datetime.now(UTC)
        scored: list[tuple[uuid.UUID, str, str, float]] = []  # (db_id, type, id, score)
        for db_id, art_type, art_id, cosine_sim in candidates:
            affinity = self._role_affinity(role, art_type)
            recency = await self._recency_decay(db_id, now)
            centrality = await self._graph_centrality(db_id)
            score = (
                settings.context_semantic_weight * cosine_sim
                + settings.context_affinity_weight * affinity
                + settings.context_recency_weight * recency
                + settings.context_graph_weight * centrality
            )
            scored.append((db_id, art_type, art_id, score))

        # Sort by composite score descending
        scored.sort(key=lambda x: x[3], reverse=True)

        # Check for contradiction pairs: if an artifact has a contradicts relation,
        # ensure both sides are included
        contradiction_ids = set()
        try:
            async with self._session_factory() as session:
                for db_id, _, _, _ in scored[:20]:
                    stmt = select(ArtifactRelation.target_id).where(
                        ArtifactRelation.source_id == db_id,
                        ArtifactRelation.relation_type == "contradicts",
                        ArtifactRelation.confidence >= settings.contradiction_confidence_threshold,
                    )
                    rows = (await session.execute(stmt)).scalars().all()
                    for target_id in rows:
                        contradiction_ids.add(target_id)
        except Exception:
            pass

        # Greedy bin-packing into budget
        import tiktoken
        encoder = tiktoken.encoding_for_model("text-embedding-3-small")

        header_tokens = len(encoder.encode(header))
        remaining = budget - header_tokens
        if remaining <= 0:
            return header

        parts: list[str] = [header]
        used_ids: set[uuid.UUID] = set()

        # Process scored artifacts + contradiction partners
        all_to_include = list(scored)
        for cid in contradiction_ids:
            if not any(s[0] == cid for s in all_to_include):
                all_to_include.append((cid, "", "", 0.0))

        for db_id, art_type, art_id, score in all_to_include:
            if db_id in used_ids:
                continue
            if remaining <= 0:
                break

            # Fetch content at appropriate level based on score
            content = await self._fetch_artifact_content(db_id, score)
            if not content:
                continue

            entry = f"\n[{art_type}/{art_id}] (score={score:.2f})\n{content}"
            entry_tokens = len(encoder.encode(entry))
            if entry_tokens > remaining:
                # Try truncated version
                char_limit = remaining * 4
                entry = entry[:char_limit]
                entry_tokens = len(encoder.encode(entry))
                if entry_tokens > remaining:
                    continue

            parts.append(entry)
            remaining -= entry_tokens
            used_ids.add(db_id)

        return "\n".join(parts)

    async def _fetch_artifact_content(
        self, db_id: uuid.UUID, score: float
    ) -> str | None:
        """Fetch artifact content from DB, choosing level based on relevance score."""
        try:
            async with self._session_factory() as session:
                art = await session.get(Artifact, db_id)
                if art is None:
                    return None
                # High score -> L2 (full), medium -> L1, low -> L0
                if score >= 0.6 and art.content_l2:
                    return art.content_l2[:3000]
                if score >= 0.3 and art.content_l1:
                    return art.content_l1[:1000]
                if art.content_l0:
                    return art.content_l0[:300]
                if art.content_l1:
                    return art.content_l1[:500]
                if art.content_l2:
                    return art.content_l2[:500]
                return None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # New: relation queries
    # ------------------------------------------------------------------

    async def get_relations(
        self,
        artifact_db_id: uuid.UUID,
        relation_type: str | None = None,
    ) -> list[ArtifactRelation]:
        try:
            async with self._session_factory() as session:
                stmt = select(ArtifactRelation).where(
                    (ArtifactRelation.source_id == artifact_db_id)
                    | (ArtifactRelation.target_id == artifact_db_id)
                )
                if relation_type:
                    stmt = stmt.where(ArtifactRelation.relation_type == relation_type)
                return list((await session.execute(stmt)).scalars().all())
        except Exception:
            logger.warning("[SemanticBoard] get_relations failed", exc_info=True)
            return []

    async def get_contradiction_pairs(self) -> list[tuple[uuid.UUID, uuid.UUID, float]]:
        """Return (source_id, target_id, confidence) for contradictions."""
        try:
            async with self._session_factory() as session:
                stmt = select(
                    ArtifactRelation.source_id,
                    ArtifactRelation.target_id,
                    ArtifactRelation.confidence,
                ).where(
                    ArtifactRelation.relation_type == "contradicts",
                    ArtifactRelation.confidence >= settings.contradiction_confidence_threshold,
                )
                rows = (await session.execute(stmt)).fetchall()
                return [(r[0], r[1], float(r[2])) for r in rows]
        except Exception:
            logger.warning("[SemanticBoard] get_contradiction_pairs failed", exc_info=True)
            return []

    async def get_support_chain(self, artifact_db_id: uuid.UUID) -> list[uuid.UUID]:
        """BFS on 'supports' relations to find the support chain."""
        visited: set[uuid.UUID] = set()
        queue = [artifact_db_id]
        chain: list[uuid.UUID] = []
        try:
            async with self._session_factory() as session:
                while queue:
                    current = queue.pop(0)
                    if current in visited:
                        continue
                    visited.add(current)
                    chain.append(current)
                    stmt = select(ArtifactRelation.source_id).where(
                        ArtifactRelation.target_id == current,
                        ArtifactRelation.relation_type == "supports",
                    )
                    rows = (await session.execute(stmt)).scalars().all()
                    for src_id in rows:
                        if src_id not in visited:
                            queue.append(src_id)
        except Exception:
            logger.warning("[SemanticBoard] get_support_chain failed", exc_info=True)
        return chain

    # ------------------------------------------------------------------
    # New: coverage gap detection
    # ------------------------------------------------------------------

    async def compute_coverage(self) -> KnowledgeState | None:
        """Decompose topic into subtopics and check artifact coverage."""
        meta = await self.get_project_meta()
        research_topic = meta.get("research_topic", "")
        if not research_topic:
            return None

        subtopics = await self._decompose_topic(research_topic)
        if not subtopics:
            return None

        gaps: list[str] = []
        covered = 0
        for subtopic in subtopics:
            matches = await self.find_relevant_artifacts(subtopic, top_k=1)
            if matches and matches[0][3] >= 0.5:
                covered += 1
            else:
                gaps.append(subtopic)

        total = len(subtopics)
        coverage = covered / total if total > 0 else 0.0

        phase = meta.get("phase", "explore")
        iteration = meta.get("iteration", 0)

        ks = KnowledgeState(
            project_id=uuid.UUID(self._project_id),
            phase=phase,
            iteration=iteration,
            coverage=coverage,
            gap_count=len(gaps),
            gap_descriptions=gaps,
        )

        try:
            async with self._session_factory() as session:
                session.add(ks)
                await session.commit()
            logger.info(
                "[SemanticBoard] Coverage: %.1f%% (%d/%d subtopics), %d gaps",
                coverage * 100, covered, total, len(gaps),
            )
        except Exception:
            logger.warning("[SemanticBoard] Failed to persist KnowledgeState", exc_info=True)

        return ks

    async def get_coverage_gaps(self) -> list[str]:
        """Return gap subtopics from the most recent coverage computation."""
        try:
            async with self._session_factory() as session:
                stmt = (
                    select(KnowledgeState)
                    .where(KnowledgeState.project_id == uuid.UUID(self._project_id))
                    .order_by(KnowledgeState.created_at.desc())
                    .limit(1)
                )
                ks = (await session.execute(stmt)).scalar_one_or_none()
                if ks and ks.gap_descriptions:
                    return ks.gap_descriptions if isinstance(ks.gap_descriptions, list) else []
        except Exception:
            logger.warning("[SemanticBoard] get_coverage_gaps failed", exc_info=True)
        return []

    # ------------------------------------------------------------------
    # New: event bus access
    # ------------------------------------------------------------------

    async def get_pending_events(self) -> list[ArtifactEvent]:
        return await self._event_bus.drain()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _persist_to_db(
        self,
        artifact_type: ArtifactType,
        artifact_id: str,
        version: int,
        content_l2: str,
        meta: ArtifactMeta,
    ) -> uuid.UUID | None:
        """INSERT artifact into PostgreSQL. Returns the DB UUID or None on failure."""
        # Read L0/L1 from filesystem if available
        ver_dir = self._artifact_dir(artifact_type, artifact_id) / f"v{version}"
        l0 = await self._read_text(ver_dir / "l0.txt")
        l1_data = await self._read_json(ver_dir / "l1.json")
        l1_str = json.dumps(l1_data, ensure_ascii=False) if l1_data else None

        db_id = uuid.uuid4()
        artifact = Artifact(
            id=db_id,
            project_id=uuid.UUID(self._project_id),
            artifact_type=artifact_type.value,
            artifact_id=artifact_id,
            version=version,
            content_l0=l0,
            content_l1=l1_str,
            content_l2=content_l2[:50000] if content_l2 else None,
            phase_created=None,
            created_by=meta.created_by.value if meta.created_by else None,
            superseded=meta.superseded,
        )
        try:
            async with self._session_factory() as session:
                session.add(artifact)
                await session.commit()
            logger.debug(
                "[SemanticBoard] Persisted artifact %s/%s v%d to DB (id=%s)",
                artifact_type.value, artifact_id, version, db_id,
            )
            return db_id
        except Exception:
            logger.warning(
                "[SemanticBoard] DB persist failed for %s/%s v%d",
                artifact_type.value, artifact_id, version,
                exc_info=True,
            )
            return None

    @staticmethod
    def _extract_embed_text(content_l2: str) -> str:
        """Extract plain text from L2 content for embedding.

        L2 content is typically a JSON string with title/body/text fields.
        Embedding the raw JSON (with braces, quotes, keys) degrades
        similarity accuracy, so we extract the meaningful text first.
        """
        try:
            obj = safe_json_loads(content_l2)
            if isinstance(obj, dict):
                parts = []
                for key in ("title", "body", "text", "content", "hypothesis",
                            "summary", "section"):
                    val = obj.get(key)
                    if isinstance(val, str) and val.strip():
                        parts.append(val.strip())
                if parts:
                    return " ".join(parts)
                # Fallback: join all string values
                for v in obj.values():
                    if isinstance(v, str) and v.strip():
                        parts.append(v.strip())
                return " ".join(parts) if parts else content_l2
        except Exception:
            pass
        return content_l2

    async def _async_post_write(
        self,
        db_id: uuid.UUID,
        content_l2: str,
        artifact_type: ArtifactType,
    ) -> None:
        """Fire-and-forget: embed content and extract relations."""
        # 1. Compute and store embedding
        if self._embedding_service and content_l2:
            try:
                embed_text = self._extract_embed_text(content_l2)
                async with _EMBED_SEMAPHORE:
                    vec = await self._embedding_service.embed_text(embed_text[:2000])
                async with self._session_factory() as session:
                    await session.execute(
                        text(
                            "UPDATE artifacts SET embedding = CAST(:vec AS vector) "
                            "WHERE id = :id"
                        ),
                        {"vec": str(vec), "id": str(db_id)},
                    )
                    await session.commit()
                logger.debug("[SemanticBoard] Embedding stored for artifact %s", db_id)
            except Exception:
                logger.warning(
                    "[SemanticBoard] Embedding failed for artifact %s", db_id, exc_info=True
                )

        # 2. Extract relations
        try:
            async with self._session_factory() as session:
                # Get recent artifacts for relation extraction
                stmt = (
                    select(Artifact.id, Artifact.content_l1)
                    .where(
                        Artifact.project_id == uuid.UUID(self._project_id),
                        Artifact.id != db_id,
                        Artifact.superseded == False,  # noqa: E712
                    )
                    .order_by(Artifact.created_at.desc())
                    .limit(15)
                )
                rows = (await session.execute(stmt)).fetchall()
                recent = [(r[0], r[1] or "") for r in rows]

            if recent:
                # Get the L1 summary of the new artifact
                async with self._session_factory() as session:
                    art = await session.get(Artifact, db_id)
                    l1_summary = art.content_l1 or art.content_l0 or (art.content_l2 or "")[:300]

                extractor = self._get_relation_extractor()
                await extractor.extract_relations(
                    self._project_id, db_id, l1_summary, recent
                )
        except Exception:
            logger.warning(
                "[SemanticBoard] Relation extraction failed for %s", db_id, exc_info=True
            )

    @staticmethod
    def _role_affinity(role: AgentRole, artifact_type_str: str) -> float:
        """1.0 if primary, 0.5 if dependency, 0.0 otherwise."""
        try:
            art_type = ArtifactType(artifact_type_str)
        except ValueError:
            return 0.0
        primary = _ROLE_PRIMARY.get(role, set())
        if art_type in primary:
            return 1.0
        dependency = _ROLE_DEPENDENCY.get(role, set())
        if art_type in dependency:
            return 0.5
        return 0.0

    async def _recency_decay(self, db_id: uuid.UUID, now: datetime) -> float:
        """Exponential decay: exp(-lambda * hours), lambda such that 24h -> 0.5."""
        try:
            async with self._session_factory() as session:
                art = await session.get(Artifact, db_id)
                if art is None or art.created_at is None:
                    return 0.5
                delta = now - art.created_at.replace(tzinfo=UTC)
                hours = delta.total_seconds() / 3600.0
                lam = math.log(2) / 24.0  # lambda such that exp(-lam*24) = 0.5
                return math.exp(-lam * hours)
        except Exception:
            return 0.5

    async def _graph_centrality(self, db_id: uuid.UUID) -> float:
        """Normalized count of incoming supports+cites relations."""
        try:
            async with self._session_factory() as session:
                stmt = select(func.count()).where(
                    ArtifactRelation.target_id == db_id,
                    ArtifactRelation.relation_type.in_(["supports", "cites"]),
                )
                count = (await session.execute(stmt)).scalar() or 0
                # Normalize: 5+ incoming relations -> 1.0
                return min(count / 5.0, 1.0)
        except Exception:
            return 0.0

    async def _decompose_topic(self, topic: str) -> list[str]:
        """Use LLM to decompose research topic into 5-15 subtopics. Cached."""
        if self._subtopic_cache is not None:
            return self._subtopic_cache

        prompt = (
            f"Decompose this research topic into 5-15 specific subtopics that a "
            f"comprehensive research paper should cover:\n\n"
            f"Topic: {topic}\n\n"
            f'Output a JSON array of subtopic strings. Example: ["subtopic1", "subtopic2"]\n'
            f"Output raw JSON only."
        )
        try:
            raw = await self._llm_router.generate(
                settings.orchestrator_model,
                prompt,
                json_mode=True,
            )
            data = safe_json_loads(raw)
            if isinstance(data, list):
                subtopics = [str(s) for s in data if isinstance(s, str)][:15]
            elif isinstance(data, dict) and "subtopics" in data:
                subtopics = [str(s) for s in data["subtopics"] if isinstance(s, str)][:15]
            else:
                subtopics = []

            if subtopics:
                self._subtopic_cache = subtopics
                logger.info(
                    "[SemanticBoard] Decomposed topic into %d subtopics", len(subtopics)
                )
            return subtopics
        except Exception:
            logger.warning("[SemanticBoard] Topic decomposition failed", exc_info=True)
            return []
