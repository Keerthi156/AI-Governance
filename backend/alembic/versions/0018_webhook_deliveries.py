"""
Add audit_webhook_deliveries for delivery history and retries.

Revision ID: 0018_webhook_deliveries
Revises: 0017_retention_auto_purge
Create Date: 2026-07-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_webhook_deliveries"
down_revision: Union[str, None] = "0017_retention_auto_purge"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("webhook_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("http_status_code", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("response_snippet", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
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
            ["webhook_id"], ["audit_webhooks.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["audit_event_id"], ["audit_events.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_webhook_deliveries_webhook_id",
        "audit_webhook_deliveries",
        ["webhook_id"],
    )
    op.create_index(
        "ix_audit_webhook_deliveries_status_retry",
        "audit_webhook_deliveries",
        ["status", "next_retry_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_audit_webhook_deliveries_status_retry",
        table_name="audit_webhook_deliveries",
    )
    op.drop_index(
        "ix_audit_webhook_deliveries_webhook_id",
        table_name="audit_webhook_deliveries",
    )
    op.drop_table("audit_webhook_deliveries")
