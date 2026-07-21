"""
Enhance evaluation tables with structure/relevance metrics and task metadata.

Revision ID: 0004_enhanced_evaluation
Revises: 0003_routing
Create Date: 2026-07-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_enhanced_evaluation"
down_revision: Union[str, None] = "0003_routing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evaluation_runs",
        sa.Column("task_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("metric_weights", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("score_gap", sa.Numeric(precision=8, scale=4), nullable=True),
    )
    op.create_index(
        "ix_evaluation_runs_task_type",
        "evaluation_runs",
        ["task_type"],
        unique=False,
    )

    op.add_column(
        "evaluation_scores",
        sa.Column(
            "structure_score",
            sa.Numeric(precision=8, scale=4),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "evaluation_scores",
        sa.Column(
            "relevance_score",
            sa.Numeric(precision=8, scale=4),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("evaluation_scores", "relevance_score")
    op.drop_column("evaluation_scores", "structure_score")
    op.drop_index("ix_evaluation_runs_task_type", table_name="evaluation_runs")
    op.drop_column("evaluation_runs", "score_gap")
    op.drop_column("evaluation_runs", "metric_weights")
    op.drop_column("evaluation_runs", "task_type")
