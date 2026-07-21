"""Analytics response schemas."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class AnalyticsSummary(BaseModel):
    total_requests: int
    success_count: int
    error_count: int
    success_rate: float = Field(..., description="0..1")
    total_tokens: int
    total_estimated_cost_usd: Decimal
    avg_latency_ms: float | None
    arena_run_count: int
    routing_decision_count: int
    evaluation_count: int


class UsageByDayItem(BaseModel):
    day: date
    requests: int
    success_count: int
    error_count: int
    tokens: int
    estimated_cost_usd: Decimal


class UsageByProviderItem(BaseModel):
    provider: str
    requests: int
    success_count: int
    error_count: int
    success_rate: float
    tokens: int
    estimated_cost_usd: Decimal
    avg_latency_ms: float | None


class UsageByModelItem(BaseModel):
    provider: str
    model: str
    requests: int
    tokens: int
    estimated_cost_usd: Decimal
    avg_latency_ms: float | None


class RoutingByTaskItem(BaseModel):
    task_type: str
    count: int


class StatusBreakdownItem(BaseModel):
    status: str
    count: int


class AnalyticsOverviewResponse(BaseModel):
    organization_slug: str
    days: int
    summary: AnalyticsSummary
    usage_by_day: list[UsageByDayItem]
    usage_by_provider: list[UsageByProviderItem]
    usage_by_model: list[UsageByModelItem]
    status_breakdown: list[StatusBreakdownItem]
    routing_by_task_type: list[RoutingByTaskItem]
