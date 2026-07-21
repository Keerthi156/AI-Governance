"""
Org-scoped LLM provider credentials (BYOK).

Why this exists:
- Multi-tenant deployments cannot share one platform API key.
- Ciphertext only is stored; plaintext is decrypted at call time.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OrganizationProviderCredential(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Encrypted provider API key for one organization."""

    __tablename__ = "organization_provider_credentials"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider",
            name="uq_org_provider_credentials_org_provider",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # groq | openai | claude | gemini
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    key_hint: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="",
        server_default="",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization = relationship("Organization", back_populates="provider_credentials")

    def __repr__(self) -> str:
        return (
            f"<OrganizationProviderCredential org={self.organization_id!r} "
            f"provider={self.provider!r}>"
        )
