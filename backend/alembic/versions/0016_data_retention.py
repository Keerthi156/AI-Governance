"""
Add data retention day columns to organizations.

Revision ID: 0016_data_retention
Revises: 0015_audit_webhooks
Create Date: 2026-07-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_data_retention"
down_revision: Union[str, None] = "0015_audit_webhooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("prompt_history_retention_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("audit_events_retention_days", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organizations", "audit_events_retention_days")
    op.drop_column("organizations", "prompt_history_retention_days")
