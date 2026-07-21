"""
Governance policy model.

Why this exists:
- Organizations need enforceable guardrails on providers, models, tokens, and prompts.
- Rules are JSONB so new constraint types can ship without schema churn.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GovernancePolicy(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Organization-scoped AI usage policy evaluated before LLM calls."""

    __tablename__ = "governance_policies"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    # Rules shape documented in schemas/governance.py PolicyRules.
    rules: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    organization = relationship("Organization", back_populates="governance_policies")

    def __repr__(self) -> str:
        return f"<GovernancePolicy name={self.name!r} active={self.is_active}>"
