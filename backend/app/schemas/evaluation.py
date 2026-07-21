"""Evaluation API schemas (enhanced)."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

EvaluationStrategy = Literal[
    "balanced",
    "cheapest",
    "fastest",
    "quality",
    "reliability",
]


class EvaluationScoreItem(BaseModel):
    id: UUID
    history_id: UUID
    provider: str
    model: str
    status: str
    success_score: Decimal
    latency_score: Decimal
    cost_score: Decimal
    substance_score: Decimal
    structure_score: Decimal = Decimal("0")
    relevance_score: Decimal = Decimal("0")
    composite_score: Decimal
    rank: int
    rationale: str | None = None


class EvaluationResponse(BaseModel):
    id: UUID
    arena_run_id: UUID
    strategy: str
    task_type: str | None = None
    metric_weights: dict[str, Any] | None = None
    score_gap: Decimal | None = None
    recommended_history_id: UUID | None
    recommended_provider: str | None
    recommended_model: str | None
    summary: str | None
    scores: list[EvaluationScoreItem]
    created_at: datetime


class EvaluateArenaBody(BaseModel):
    arena_run_id: UUID
    strategy: EvaluationStrategy = Field(default="balanced")
    task_type: str | None = Field(
        default=None,
        description="Optional router task type for task-aware weight overlays",
    )


class CompareStrategiesBody(BaseModel):
    arena_run_id: UUID
    task_type: str | None = None
    strategies: list[EvaluationStrategy] | None = Field(
        default=None,
        description="Defaults to all strategies when omitted",
    )


class StrategyComparisonResponse(BaseModel):
    arena_run_id: UUID
    evaluations: list[EvaluationResponse]
