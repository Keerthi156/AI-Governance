"""
Outbound audit webhooks — notify external systems of org audit events.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuditWebhook(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """HTTPS endpoint that receives audit event payloads for an organization."""

    __tablename__ = "audit_webhooks"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    # Fernet-encrypted HMAC signing secret
    secret_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    secret_hint: Mapped[str] = mapped_column(String(32), nullable=False, server_default="")
    # Empty list / null = subscribe to all actions
    action_filters: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    last_delivery_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization = relationship("Organization", back_populates="audit_webhooks")
    deliveries = relationship(
        "AuditWebhookDelivery",
        back_populates="webhook",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<AuditWebhook name={self.name!r} active={self.is_active!r}>"


class AuditWebhookDelivery(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One delivery attempt (or pending retry) for a webhook + audit event."""

    __tablename__ = "audit_webhook_deliveries"

    webhook_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("audit_webhooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    audit_event_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("audit_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # pending | success | failed | exhausted
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    webhook = relationship("AuditWebhook", back_populates="deliveries")

    def __repr__(self) -> str:
        return (
            f"<AuditWebhookDelivery status={self.status!r} "
            f"attempt={self.attempt_number!r}>"
        )
