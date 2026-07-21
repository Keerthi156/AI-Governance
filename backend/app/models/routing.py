"""
Routing decision persistence.

Why this exists:
- Governance needs an audit trail of why a model was chosen.
- Analytics can measure router accuracy vs Arena evaluation later.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RoutingDecision(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One Intelligent Task Router decision (classify + recommend)."""

    __tablename__ = "routing_decisions"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    preference: Mapped[str] = mapped_column(String(30), nullable=False, default="balanced")

    recommended_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    recommended_model: Mapped[str] = mapped_column(String(100), nullable=False)

    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    candidates: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    matched_signals: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    executed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    history_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("prompt_history.id", ondelete="SET NULL"),
        nullable=True,
    )
