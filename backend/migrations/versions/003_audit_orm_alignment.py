"""Audit fixes: align ORM models with Pydantic types (D07/D08/D09).

Revision ID: 003_audit_orm_alignment
Revises: 002_phase1_tables
Create Date: 2026-03-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_audit_orm_alignment"
down_revision: str | None = "002_phase1_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # D07: evaluation_results — rename fields to match PhaseEvaluation Pydantic model
    # evaluator_role -> evaluator_model (was String(50), now String(100))
    op.alter_column("evaluation_results", "evaluator_role", new_column_name="evaluator_model")
    op.alter_column(
        "evaluation_results", "evaluator_model", type_=sa.String(100), existing_type=sa.String(50)
    )
    # Add evaluator_provider column
    op.add_column(
        "evaluation_results",
        sa.Column("evaluator_provider", sa.String(50), nullable=True),
    )
    # scores -> dimensions (JSON field, same type)
    op.alter_column("evaluation_results", "scores", new_column_name="dimensions")
    # overall_score -> composite_score (Float, same type)
    op.alter_column("evaluation_results", "overall_score", new_column_name="composite_score")
    # feedback (Text) -> raw_evidence (JSON)
    op.drop_column("evaluation_results", "feedback")
    op.add_column(
        "evaluation_results",
        sa.Column("raw_evidence", sa.JSON, nullable=True),
    )

    # D08: knowledge_state — add missing gap fields
    op.add_column(
        "knowledge_state",
        sa.Column("gap_count", sa.Integer, server_default="0"),
    )
    op.add_column(
        "knowledge_state",
        sa.Column("gap_descriptions", sa.JSON, nullable=True),
    )

    # D09: iteration_metrics — add missing fields, make agent_role nullable
    op.alter_column("iteration_metrics", "agent_role", nullable=True)
    op.add_column(
        "iteration_metrics",
        sa.Column("information_gain", sa.Float, nullable=True),
    )
    op.add_column(
        "iteration_metrics",
        sa.Column("artifact_count_delta", sa.Integer, nullable=True),
    )
    op.add_column(
        "iteration_metrics",
        sa.Column("unique_claim_delta", sa.Integer, nullable=True),
    )
    op.add_column(
        "iteration_metrics",
        sa.Column("eval_composite", sa.Float, nullable=True),
    )


def downgrade() -> None:
    # iteration_metrics — remove added columns
    op.drop_column("iteration_metrics", "eval_composite")
    op.drop_column("iteration_metrics", "unique_claim_delta")
    op.drop_column("iteration_metrics", "artifact_count_delta")
    op.drop_column("iteration_metrics", "information_gain")
    op.alter_column("iteration_metrics", "agent_role", nullable=False)

    # knowledge_state — remove gap fields
    op.drop_column("knowledge_state", "gap_descriptions")
    op.drop_column("knowledge_state", "gap_count")

    # evaluation_results — reverse changes
    op.drop_column("evaluation_results", "raw_evidence")
    op.add_column(
        "evaluation_results",
        sa.Column("feedback", sa.Text, nullable=True),
    )
    op.alter_column("evaluation_results", "composite_score", new_column_name="overall_score")
    op.alter_column("evaluation_results", "dimensions", new_column_name="scores")
    op.drop_column("evaluation_results", "evaluator_provider")
    op.alter_column(
        "evaluation_results", "evaluator_model", type_=sa.String(50), existing_type=sa.String(100)
    )
    op.alter_column("evaluation_results", "evaluator_model", new_column_name="evaluator_role")
