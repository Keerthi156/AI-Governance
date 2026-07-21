"""
Create organization_memberships and backfill from users.organization_id.

Revision ID: 0012_organization_memberships
Revises: 0011_prompt_templates
Create Date: 2026-07-20
"""

from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import table, column

revision: str = "0012_organization_memberships"
down_revision: Union[str, None] = "0011_prompt_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=50), server_default="member", nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "organization_id",
            name="uq_organization_memberships_user_org",
        ),
    )
    op.create_index(
        "ix_organization_memberships_user_id",
        "organization_memberships",
        ["user_id"],
    )
    op.create_index(
        "ix_organization_memberships_organization_id",
        "organization_memberships",
        ["organization_id"],
    )

    conn = op.get_bind()
    users = conn.execute(sa.text("SELECT id, organization_id, role FROM users")).mappings()
    memberships = table(
        "organization_memberships",
        column("id", postgresql.UUID),
        column("user_id", postgresql.UUID),
        column("organization_id", postgresql.UUID),
        column("role", sa.String),
    )
    rows = [
        {
            "id": uuid4(),
            "user_id": row["id"],
            "organization_id": row["organization_id"],
            "role": row["role"] or "member",
        }
        for row in users
    ]
    if rows:
        op.bulk_insert(memberships, rows)


def downgrade() -> None:
    op.drop_index(
        "ix_organization_memberships_organization_id",
        table_name="organization_memberships",
    )
    op.drop_index(
        "ix_organization_memberships_user_id",
        table_name="organization_memberships",
    )
    op.drop_table("organization_memberships")
