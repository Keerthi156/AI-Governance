"""
Prompt history model.

Why this exists:
- Arena Mode and single-model calls need durable prompt/response records.
- Token counts and estimated cost land here for analytics (Phase 1–2).
- Provider/model columns stay nullable-friendly for partial failures.
"""

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class PromptHistory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single LLM interaction (or one side of an Arena comparison)."""

    __tablename__ = "prompt_history"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status: pending | success | error
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Stored as NUMERIC for accurate money math (avoid float).
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6),
        nullable=True,
    )

    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Optional link for Arena Mode: same arena_run_id groups multi-model replies.
    arena_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="prompt_history",
    )

    def __repr__(self) -> str:
        return f"<PromptHistory provider={self.provider!r} model={self.model!r}>"
