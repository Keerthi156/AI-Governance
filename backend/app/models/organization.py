"""
Organization model.

Why this exists:
- Enterprise platforms are multi-tenant; prompts/costs/policies belong to an org.
- Scaffolding now avoids painful migrations once auth (Phase 3) lands.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A customer / tenant account on the platform."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # None = retain indefinitely
    prompt_history_retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audit_events_retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Opt-in: platform scheduler may purge expired rows for this org.
    retention_auto_purge_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    retention_last_auto_purge_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    prompt_history = relationship(
        "PromptHistory",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    users = relationship(
        "User",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    memberships = relationship(
        "OrganizationMembership",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    api_keys = relationship(
        "ApiKey",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    provider_credentials = relationship(
        "OrganizationProviderCredential",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    audit_webhooks = relationship(
        "AuditWebhook",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    governance_policies = relationship(
        "GovernancePolicy",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    audit_events = relationship(
        "AuditEvent",
        back_populates="organization",
    )
    rag_documents = relationship(
        "RagDocument",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    agent_definitions = relationship(
        "AgentDefinition",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    agent_runs = relationship(
        "AgentRun",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    invites = relationship(
        "OrganizationInvite",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Organization slug={self.slug!r}>"
