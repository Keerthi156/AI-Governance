"""
Add evaluation_runs and evaluation_scores tables.

Revision ID: 0002_evaluation
Revises: 0001_initial_schema
Create Date: 2026-07-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_evaluation"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("arena_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy", sa.String(length=50), nullable=False),
        sa.Column("recommended_history_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recommended_provider", sa.String(length=50), nullable=True),
        sa.Column("recommended_model", sa.String(length=100), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["recommended_history_id"],
            ["prompt_history.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_evaluation_runs_arena_run_id",
        "evaluation_runs",
        ["arena_run_id"],
        unique=False,
    )

    op.create_table(
        "evaluation_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("history_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("success_score", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("latency_score", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("cost_score", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("substance_score", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("composite_score", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"],
            ["evaluation_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["history_id"],
            ["prompt_history.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_evaluation_scores_evaluation_run_id",
        "evaluation_scores",
        ["evaluation_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_evaluation_scores_history_id",
        "evaluation_scores",
        ["history_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_evaluation_scores_history_id", table_name="evaluation_scores")
    op.drop_index(
        "ix_evaluation_scores_evaluation_run_id",
        table_name="evaluation_scores",
    )
    op.drop_table("evaluation_scores")
    op.drop_index("ix_evaluation_runs_arena_run_id", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
