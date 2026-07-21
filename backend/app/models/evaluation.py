"""
Evaluation run + per-participant score models.

Why this exists:
- Arena comparisons need durable, explainable rankings for governance/analytics.
- Recommendations are auditable (strategy + score breakdown stored).
"""

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.prompt_history import PromptHistory


class EvaluationRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One evaluation pass over an Arena run (or multi-history set)."""

    __tablename__ = "evaluation_runs"

    arena_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    strategy: Mapped[str] = mapped_column(String(50), nullable=False, default="balanced")
    task_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    metric_weights: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    score_gap: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    recommended_history_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("prompt_history.id", ondelete="SET NULL"),
        nullable=True,
    )
    recommended_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    recommended_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    scores = relationship(
        "EvaluationScore",
        back_populates="evaluation_run",
        cascade="all, delete-orphan",
        order_by="EvaluationScore.rank",
    )


class EvaluationScore(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Scorecard for one prompt_history row inside an evaluation run."""

    __tablename__ = "evaluation_scores"

    evaluation_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    history_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("prompt_history.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)

    success_score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    latency_score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    cost_score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    substance_score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    structure_score: Mapped[Decimal] = mapped_column(
        Numeric(8, 4),
        nullable=False,
        default=Decimal("0"),
    )
    relevance_score: Mapped[Decimal] = mapped_column(
        Numeric(8, 4),
        nullable=False,
        default=Decimal("0"),
    )
    composite_score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    evaluation_run = relationship("EvaluationRun", back_populates="scores")
    history: Mapped["PromptHistory"] = relationship("PromptHistory")
