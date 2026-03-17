"""Phase 1: pgvector extension + 11 new tables.

Revision ID: 002_phase1_tables
Revises: 001_baseline
Create Date: 2026-03-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "002_phase1_tables"
down_revision: str | None = "001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 4096


def upgrade() -> None:
    # Enable pgvector
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 1. artifacts
    op.create_table(
        "artifacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_type", sa.String(50), nullable=False),
        sa.Column("artifact_id", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("content_l0", sa.Text, nullable=True),
        sa.Column("content_l1", sa.Text, nullable=True),
        sa.Column("content_l2", sa.Text, nullable=True),
        sa.Column("quality_score", sa.Float, nullable=True),
        sa.Column("phase_created", sa.String(50), nullable=True),
        sa.Column("created_by", sa.String(50), nullable=True),
        sa.Column("superseded", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_artifacts_project_id", "artifacts", ["project_id"])
    op.create_index("ix_artifacts_artifact_type", "artifacts", ["artifact_type"])
    # Add vector column via raw SQL (Alembic doesn't know pgvector types natively)
    op.execute(f"ALTER TABLE artifacts ADD COLUMN embedding vector({EMBEDDING_DIM})")

    # 2. artifact_relations
    op.create_table(
        "artifact_relations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id",
            UUID(as_uuid=True),
            sa.ForeignKey("artifacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_id",
            UUID(as_uuid=True),
            sa.ForeignKey("artifacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float, server_default="1.0"),
        sa.Column("evidence", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_artifact_relations_source_id", "artifact_relations", ["source_id"])
    op.create_index("ix_artifact_relations_target_id", "artifact_relations", ["target_id"])

    # 3. evaluation_results
    op.create_table(
        "evaluation_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "artifact_id",
            UUID(as_uuid=True),
            sa.ForeignKey("artifacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("evaluator_role", sa.String(50), nullable=False),
        sa.Column("phase", sa.String(50), nullable=False),
        sa.Column("iteration", sa.Integer, nullable=False),
        sa.Column("scores", sa.JSON, nullable=True),
        sa.Column("overall_score", sa.Float, nullable=True),
        sa.Column("feedback", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_evaluation_results_project_id", "evaluation_results", ["project_id"])

    # 4. knowledge_state
    op.create_table(
        "knowledge_state",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phase", sa.String(50), nullable=False),
        sa.Column("iteration", sa.Integer, nullable=False),
        sa.Column("coverage", sa.Float, server_default="0.0"),
        sa.Column("density", sa.Float, server_default="0.0"),
        sa.Column("coherence", sa.Float, server_default="0.0"),
        sa.Column("snapshot", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_knowledge_state_project_id", "knowledge_state", ["project_id"])

    # 5. messages
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sender_role", sa.String(50), nullable=False),
        sa.Column("recipient_role", sa.String(50), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("phase", sa.String(50), nullable=True),
        sa.Column("iteration", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_messages_project_id", "messages", ["project_id"])

    # 6. challenges
    op.create_table(
        "challenges",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("challenge_id", sa.String(255), nullable=False, unique=True),
        sa.Column("challenger_role", sa.String(50), nullable=False),
        sa.Column("target_artifact", sa.String(255), nullable=True),
        sa.Column("target_agent_role", sa.String(50), nullable=True),
        sa.Column("argument", sa.Text, nullable=False),
        sa.Column("status", sa.String(50), server_default="open"),
        sa.Column("resolution", sa.Text, nullable=True),
        sa.Column("resolved_by", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_challenges_project_id", "challenges", ["project_id"])

    # 7. project_settings
    op.create_table(
        "project_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_project_settings_project_id", "project_settings", ["project_id"])
    op.create_index("ix_project_settings_key", "project_settings", ["key"])

    # 8. claims
    op.create_table(
        "claims",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "artifact_id",
            UUID(as_uuid=True),
            sa.ForeignKey("artifacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, server_default="1.0"),
        sa.Column("source_agent", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_claims_project_id", "claims", ["project_id"])
    # Add vector column for claim embeddings
    op.execute(f"ALTER TABLE claims ADD COLUMN embedding vector({EMBEDDING_DIM})")

    # 9. contradictions
    op.create_table(
        "contradictions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "claim_a_id",
            UUID(as_uuid=True),
            sa.ForeignKey("claims.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "claim_b_id",
            UUID(as_uuid=True),
            sa.ForeignKey("claims.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float, server_default="0.0"),
        sa.Column("evidence", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), server_default="detected"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_contradictions_project_id", "contradictions", ["project_id"])

    # 10. info_requests
    op.create_table(
        "info_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requester_role", sa.String(50), nullable=False),
        sa.Column("responder_role", sa.String(50), nullable=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("response", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_info_requests_project_id", "info_requests", ["project_id"])

    # 11. iteration_metrics
    op.create_table(
        "iteration_metrics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phase", sa.String(50), nullable=False),
        sa.Column("iteration", sa.Integer, nullable=False),
        sa.Column("agent_role", sa.String(50), nullable=False),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("artifacts_produced", sa.Integer, nullable=True),
        sa.Column("critic_score", sa.Float, nullable=True),
        sa.Column("metrics", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_iteration_metrics_project_id", "iteration_metrics", ["project_id"])


def downgrade() -> None:
    op.drop_table("iteration_metrics")
    op.drop_table("info_requests")
    op.drop_table("contradictions")
    op.drop_table("claims")
    op.drop_table("project_settings")
    op.drop_table("challenges")
    op.drop_table("messages")
    op.drop_table("knowledge_state")
    op.drop_table("evaluation_results")
    op.drop_table("artifact_relations")
    op.drop_table("artifacts")
    op.execute("DROP EXTENSION IF EXISTS vector")
