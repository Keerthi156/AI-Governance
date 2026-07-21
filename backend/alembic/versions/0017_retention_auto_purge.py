"""
Add per-org opt-in auto-purge columns for scheduled retention.

Revision ID: 0017_retention_auto_purge
Revises: 0016_data_retention
Create Date: 2026-07-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_retention_auto_purge"
down_revision: Union[str, None] = "0016_data_retention"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "retention_auto_purge_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "organizations",
        sa.Column("retention_last_auto_purge_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organizations", "retention_last_auto_purge_at")
    op.drop_column("organizations", "retention_auto_purge_enabled")
