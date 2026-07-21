"""
Organization membership — users may belong to multiple tenants.

Why this exists:
- Org switcher must list only orgs the caller can access.
- organization_slug on APIs must not grant cross-tenant access by guessing slugs.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OrganizationMembership(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Link between a user and an organization they may access."""

    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "organization_id",
            name="uq_organization_memberships_user_org",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Per-tenant role for membership admin checks (JWT still uses users.role).
    role: Mapped[str] = mapped_column(String(50), nullable=False, server_default="member")

    user = relationship("User", back_populates="memberships")
    organization = relationship("Organization", back_populates="memberships")

    def __repr__(self) -> str:
        return (
            f"<OrganizationMembership user={self.user_id!r} "
            f"org={self.organization_id!r} role={self.role!r}>"
        )
