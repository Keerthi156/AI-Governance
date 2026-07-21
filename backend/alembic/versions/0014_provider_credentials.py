"""
Create organization_provider_credentials for BYOK LLM keys.

Revision ID: 0014_provider_credentials
Revises: 0013_api_keys
Create Date: 2026-07-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_provider_credentials"
down_revision: Union[str, None] = "0013_api_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization_provider_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("key_hint", sa.String(length=32), server_default="", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "provider",
            name="uq_org_provider_credentials_org_provider",
        ),
    )
    op.create_index(
        "ix_organization_provider_credentials_organization_id",
        "organization_provider_credentials",
        ["organization_id"],
    )
    op.create_index(
        "ix_organization_provider_credentials_provider",
        "organization_provider_credentials",
        ["provider"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_organization_provider_credentials_provider",
        table_name="organization_provider_credentials",
    )
    op.drop_index(
        "ix_organization_provider_credentials_organization_id",
        table_name="organization_provider_credentials",
    )
    op.drop_table("organization_provider_credentials")
