"""
AI agent definition and run models.

Why this exists:
- Enterprise agent workflows need durable definitions and auditable run logs.
- Steps are a fixed tool plan (v1) — no LangChain; easy to evolve into a planner later.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentDefinition(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Org-scoped agent recipe: ordered tools + default model settings."""

    __tablename__ = "agent_definitions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Ordered list of tool names, e.g. ["classify_task", "rag_search", "llm_answer"]
    steps: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    default_provider: Mapped[str] = mapped_column(String(50), nullable=False, server_default="groq")
    default_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    max_steps: Mapped[int] = mapped_column(Integer, nullable=False, server_default="8")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    organization = relationship("Organization", back_populates="agent_definitions")
    runs = relationship(
        "AgentRun",
        back_populates="definition",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<AgentDefinition name={self.name!r}>"


class AgentRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One execution of an agent definition against a user input."""

    __tablename__ = "agent_runs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="pending")
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # [{step, tool, status, summary, detail}]
    steps_log: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")

    definition = relationship("AgentDefinition", back_populates="runs")
    organization = relationship("Organization", back_populates="agent_runs")

    def __repr__(self) -> str:
        return f"<AgentRun status={self.status!r} def={self.definition_id}>"
