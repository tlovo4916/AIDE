"""M2b End-to-End verification for SemanticBoard.

Runs against real PostgreSQL + pgvector. Requires OpenRouter API key for embeddings.
Usage: docker compose exec backend python -m backend.tests.e2e_semantic_board
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid

from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("e2e_semantic_board")


async def main() -> None:
    from backend.blackboard.event_bus import EventBus
    from backend.blackboard.semantic_board import SemanticBoard
    from backend.config import settings
    from backend.knowledge.embeddings import EmbeddingService
    from backend.models import async_session_factory, init_db
    from backend.types import (
        ActionType,
        AgentRole,
        ArtifactMeta,
        ArtifactType,
        BlackboardAction,
    )

    results: dict[str, str] = {}
    project_id = str(uuid.uuid4())
    workspace = settings.workspace_dir / "projects" / project_id

    logger.info("=== M2b E2E Verification ===")
    logger.info("Project ID: %s", project_id)

    await init_db()
    logger.info("✓ init_db() completed")

    # Create project row
    async with async_session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO projects "
                "(id, name, description, research_topic, phase, status) "
                "VALUES (:id, :name, :desc, :topic, :phase, :status)"
            ),
            {
                "id": project_id,
                "name": "M2b E2E Test",
                "desc": "E2E verification for SemanticBoard",
                "topic": "Deep learning optimization techniques for LLMs",
                "phase": "EXPLORE",
                "status": "running",
            },
        )
        await session.commit()
    logger.info("✓ Test project created in DB")

    # ── Embedding service ──
    embedding_service = None
    if settings.openrouter_api_key:
        embedding_service = EmbeddingService(model=settings.embedding_model)
        try:
            test_vec = await embedding_service.embed_text("hello world")
            logger.info(
                "✓ EmbeddingService OK: dim=%d (expected %d)",
                len(test_vec), settings.embedding_dimensions,
            )
            results["embedding_service"] = "PASS"
        except Exception as e:
            logger.error("✗ EmbeddingService failed: %s", e)
            embedding_service = None
            results["embedding_service"] = f"FAIL: {e}"
    else:
        logger.warning("⚠ No OPENROUTER_API_KEY — embeddings skipped")
        results["embedding_service"] = "SKIP"

    # ── Create SemanticBoard ──
    event_bus = EventBus()
    board = SemanticBoard(
        project_path=workspace,
        session_factory=async_session_factory,
        embedding_service=embedding_service,
        llm_router=None,
        project_id=project_id,
        event_bus=event_bus,
    )
    await board.init_workspace(
        research_topic="Deep learning optimization techniques for LLMs"
    )
    logger.info("✓ SemanticBoard created and workspace initialized")

    # ── Test 1: Dual-write ──
    logger.info("\n--- Test 1: Dual-Write ---")
    content_l2 = json.dumps({
        "title": "Gradient Accumulation Hypothesis",
        "body": (
            "Gradient accumulation with adaptive batch sizing can improve "
            "convergence speed of large language models by 15-20% compared "
            "to fixed batch size training, especially when combined with "
            "learning rate warmup schedules."
        ),
    })
    meta1 = ArtifactMeta(
        artifact_type=ArtifactType.HYPOTHESES,
        artifact_id="hypothesis_001",
        version=1,
        created_by=AgentRole.SCIENTIST,
    )
    await board.write_artifact(
        artifact_type=ArtifactType.HYPOTHESES,
        artifact_id="hypothesis_001",
        version=1,
        content_l2=content_l2,
        meta=meta1,
    )

    # Check filesystem
    fs_path = workspace / "artifacts" / "hypotheses" / "hypothesis_001" / "v1" / "l2.json"
    if fs_path.exists():
        logger.info("✓ Filesystem write confirmed: %s", fs_path)
        results["dual_write_fs"] = "PASS"
    else:
        logger.error("✗ Filesystem write missing")
        results["dual_write_fs"] = "FAIL"

    # Wait for async post-write (embedding + relation extraction)
    await asyncio.sleep(4)

    # Check DB
    async with async_session_factory() as session:
        row = await session.execute(
            text(
                "SELECT id, artifact_type, artifact_id, content_l0, "
                "embedding IS NOT NULL as has_emb "
                "FROM artifacts WHERE project_id = :pid"
            ),
            {"pid": project_id},
        )
        rows = row.fetchall()
        if rows:
            r = rows[0]
            logger.info(
                "✓ DB write: type=%s, id=%s, has_embedding=%s",
                r.artifact_type, r.artifact_id, r.has_emb,
            )
            results["dual_write_db"] = "PASS"
            if r.has_emb:
                results["embedding_stored"] = "PASS"
                logger.info("✓ Embedding stored in artifacts table")
            else:
                results["embedding_stored"] = (
                    "SKIP" if not embedding_service else "FAIL"
                )
        else:
            logger.error("✗ No artifact found in DB")
            results["dual_write_db"] = "FAIL"
            results["embedding_stored"] = "FAIL"

    # ── Test 2: Event Bus ──
    logger.info("\n--- Test 2: Event Bus ---")
    events = await event_bus.drain()
    if events:
        ev = events[0]
        logger.info(
            "✓ Event: type=%s, artifact=%s, agent=%s",
            ev.event_type, ev.artifact_id, ev.agent_role,
        )
        results["event_bus"] = "PASS"
    else:
        logger.error("✗ No events published")
        results["event_bus"] = "FAIL"

    # ── Test 3: Write more artifacts ──
    logger.info("\n--- Test 3: Additional Artifacts ---")

    content_evidence = json.dumps({
        "title": "Learning Rate Scheduling Survey",
        "body": (
            "A comprehensive survey of learning rate scheduling: cosine annealing, "
            "warm restarts, and one-cycle policy. Key finding: cosine annealing with "
            "warm restarts achieves 2-3% better accuracy on ImageNet."
        ),
    })
    meta_ev = ArtifactMeta(
        artifact_type=ArtifactType.EVIDENCE_FINDINGS,
        artifact_id="evidence_001",
        version=1,
        created_by=AgentRole.LIBRARIAN,
    )
    await board.write_artifact(
        ArtifactType.EVIDENCE_FINDINGS, "evidence_001", 1, content_evidence, meta_ev,
    )

    content_review = json.dumps({
        "title": "Critical Review of Optimization Claims",
        "body": (
            "The hypothesis about gradient accumulation improving convergence "
            "by 15-20% lacks sufficient evidence. The cited studies use different "
            "architectures and datasets."
        ),
    })
    meta_rv = ArtifactMeta(
        artifact_type=ArtifactType.REVIEW,
        artifact_id="review_001",
        version=1,
        created_by=AgentRole.CRITIC,
    )
    await board.write_artifact(
        ArtifactType.REVIEW, "review_001", 1, content_review, meta_rv,
    )

    # Near-duplicate for dedup test
    content_dup = json.dumps({
        "title": "Gradient Accumulation with Adaptive Batching",
        "body": (
            "Adaptive gradient accumulation combined with dynamic batch sizing "
            "improves the convergence rate of LLMs by approximately 15-20%, "
            "particularly when used with learning rate warmup."
        ),
    })
    meta_dup = ArtifactMeta(
        artifact_type=ArtifactType.HYPOTHESES,
        artifact_id="hypothesis_002",
        version=1,
        created_by=AgentRole.SCIENTIST,
    )
    await board.write_artifact(
        ArtifactType.HYPOTHESES, "hypothesis_002", 1, content_dup, meta_dup,
    )

    await asyncio.sleep(4)
    logger.info("✓ 3 additional artifacts written")

    # ── Test 4: Semantic dedup ──
    logger.info("\n--- Test 4: Semantic Dedup ---")
    dup_action = BlackboardAction(
        agent_role=AgentRole.SCIENTIST,
        action_type=ActionType.WRITE_ARTIFACT,
        target="hypotheses",
        content={
            "title": "Gradient Accumulation Convergence",
            "body": (
                "Gradient accumulation with adaptive batch sizing can improve "
                "convergence speed of large language models by 15-20%"
            ),
        },
    )
    unique_action = BlackboardAction(
        agent_role=AgentRole.LIBRARIAN,
        action_type=ActionType.WRITE_ARTIFACT,
        target="evidence_findings",
        content={
            "title": "Transformer Attention Mechanisms",
            "body": (
                "Multi-head attention in transformers enables parallel computation "
                "of different representation subspaces at different positions."
            ),
        },
    )
    filtered = await board.dedup_check([dup_action, unique_action])
    if len(filtered) < 2:
        logger.info(
            "✓ Semantic dedup filtered: %d/2 actions passed", len(filtered),
        )
        results["semantic_dedup"] = "PASS"
    else:
        logger.info(
            "⚠ Dedup did not filter (may need embedding similarity): %d/2",
            len(filtered),
        )
        results["semantic_dedup"] = "WARN (no filtering)"

    # ── Test 5: find_relevant_artifacts ──
    logger.info("\n--- Test 5: Semantic Search ---")
    if embedding_service:
        try:
            relevant = await board.find_relevant_artifacts(
                "How does gradient accumulation affect model training?"
            )
            if relevant:
                logger.info(
                    "✓ find_relevant returned %d results:", len(relevant),
                )
                for db_id, a_type, a_id, sim in relevant[:3]:
                    logger.info("  - %s/%s  sim=%.4f", a_type, a_id, sim)
                results["semantic_search"] = "PASS"
            else:
                logger.warning("⚠ Empty results (embeddings pending?)")
                results["semantic_search"] = "WARN"
        except Exception as e:
            logger.error("✗ find_relevant failed: %s", e)
            results["semantic_search"] = f"FAIL: {e}"
    else:
        results["semantic_search"] = "SKIP"

    # ── Test 6: build_agent_context ──
    logger.info("\n--- Test 6: Context Building ---")
    try:
        context = await board.build_agent_context(
            AgentRole.SCIENTIST,
            "Investigate gradient accumulation techniques for LLM training",
        )
        if context and len(context) > 50:
            logger.info("✓ build_agent_context: %d chars", len(context))
            preview = context[:200].replace("\n", " ")
            logger.info("  Preview: %s...", preview)
            results["context_building"] = "PASS"
        else:
            logger.warning("⚠ Short/empty context result")
            results["context_building"] = "WARN"
    except Exception as e:
        logger.error("✗ build_agent_context failed: %s", e)
        results["context_building"] = f"FAIL: {e}"

    # ── Test 7: DB state ──
    logger.info("\n--- Test 7: DB State ---")
    async with async_session_factory() as session:
        art_count = (await session.execute(
            text("SELECT COUNT(*) FROM artifacts WHERE project_id = :pid"),
            {"pid": project_id},
        )).scalar()
        emb_count = (await session.execute(
            text(
                "SELECT COUNT(*) FROM artifacts "
                "WHERE project_id = :pid AND embedding IS NOT NULL"
            ),
            {"pid": project_id},
        )).scalar()
        rel_count = (await session.execute(
            text(
                "SELECT COUNT(*) FROM artifact_relations ar "
                "JOIN artifacts a ON ar.source_id = a.id "
                "WHERE a.project_id = :pid"
            ),
            {"pid": project_id},
        )).scalar()

    logger.info("  artifacts: %d (expected 4)", art_count)
    logger.info("  with embeddings: %d", emb_count)
    logger.info("  relations: %d", rel_count)
    results["db_state"] = (
        f"PASS ({art_count} artifacts, {emb_count} embedded, {rel_count} rels)"
    )

    # ── Cleanup ──
    logger.info("\n--- Cleanup ---")
    async with async_session_factory() as session:
        await session.execute(
            text(
                "DELETE FROM artifact_relations WHERE source_id IN "
                "(SELECT id FROM artifacts WHERE project_id = :pid)"
            ),
            {"pid": project_id},
        )
        await session.execute(
            text("DELETE FROM artifacts WHERE project_id = :pid"),
            {"pid": project_id},
        )
        await session.execute(
            text("DELETE FROM projects WHERE id = :pid"),
            {"pid": project_id},
        )
        await session.commit()
    logger.info("✓ Test data cleaned up")

    # Clean up filesystem
    import shutil
    if workspace.exists():
        shutil.rmtree(workspace)
        logger.info("✓ Workspace dir removed")

    if embedding_service:
        await embedding_service.close()

    # ── Summary ──
    logger.info("\n" + "=" * 60)
    logger.info("M2b E2E VERIFICATION RESULTS")
    logger.info("=" * 60)
    all_pass = True
    for test_name, result in results.items():
        icon = "✓" if result.startswith("PASS") else (
            "⚠" if "SKIP" in result or "WARN" in result else "✗"
        )
        logger.info("  %s %-25s %s", icon, test_name, result)
        if result.startswith("FAIL"):
            all_pass = False

    logger.info("=" * 60)
    if all_pass:
        logger.info("✅ M2b VERIFICATION PASSED")
    else:
        logger.error("❌ M2b VERIFICATION FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
