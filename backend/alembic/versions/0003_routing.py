"""
Add routing_decisions table for Intelligent Task Router.

Revision ID: 0003_routing
Revises: 0002_evaluation
Create Date: 2026-07-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_routing"
down_revision: Union[str, None] = "0002_evaluation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "routing_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("preference", sa.String(length=30), nullable=False),
        sa.Column("recommended_provider", sa.String(length=50), nullable=False),
        sa.Column("recommended_model", sa.String(length=100), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("matched_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("executed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("history_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["history_id"], ["prompt_history.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_routing_decisions_organization_id",
        "routing_decisions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_routing_decisions_task_type",
        "routing_decisions",
        ["task_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_routing_decisions_task_type", table_name="routing_decisions")
    op.drop_index("ix_routing_decisions_organization_id", table_name="routing_decisions")
    op.drop_table("routing_decisions")
