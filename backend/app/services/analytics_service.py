"""
Analytics aggregation service.

Why this exists:
- Ops/product leaders need usage, cost, and reliability visibility.
- Aggregates prompt_history + routing_decisions + evaluation_runs in one overview.
- SQL aggregates keep the hot path cheap; materialized views can come later at scale.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.evaluation import EvaluationRun
from app.models.prompt_history import PromptHistory
from app.models.routing import RoutingDecision
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    AnalyticsSummary,
    RoutingByTaskItem,
    StatusBreakdownItem,
    UsageByDayItem,
    UsageByModelItem,
    UsageByProviderItem,
)
from app.services.organization_service import get_request_actor, require_organization_access


def get_analytics_overview(
    db: Session,
    *,
    organization_slug: str = "default",
    days: int = 7,
) -> AnalyticsOverviewResponse:
    """Return KPI + chart series for the analytics dashboard."""
    days = max(1, min(days, 90))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        org = require_organization_access(db, organization_slug)
    except NotFoundError:
        if get_request_actor() is not None:
            raise
        org = None

    if org is None:
        empty_summary = AnalyticsSummary(
            total_requests=0,
            success_count=0,
            error_count=0,
            success_rate=0.0,
            total_tokens=0,
            total_estimated_cost_usd=Decimal("0"),
            avg_latency_ms=None,
            arena_run_count=0,
            routing_decision_count=0,
            evaluation_count=0,
        )
        return AnalyticsOverviewResponse(
            organization_slug=organization_slug,
            days=days,
            summary=empty_summary,
            usage_by_day=[],
            usage_by_provider=[],
            usage_by_model=[],
            status_breakdown=[],
            routing_by_task_type=[],
        )

    org_id = org.id
    ph_filters = [
        PromptHistory.organization_id == org_id,
        PromptHistory.created_at >= since,
    ]

    total_requests = (
        db.scalar(select(func.count()).select_from(PromptHistory).where(*ph_filters))
        or 0
    )
    success_count = (
        db.scalar(
            select(func.count())
            .select_from(PromptHistory)
            .where(*ph_filters, PromptHistory.status == "success")
        )
        or 0
    )
    error_count = (
        db.scalar(
            select(func.count())
            .select_from(PromptHistory)
            .where(*ph_filters, PromptHistory.status == "error")
        )
        or 0
    )
    total_tokens = (
        db.scalar(
            select(func.coalesce(func.sum(PromptHistory.total_tokens), 0)).where(
                *ph_filters
            )
        )
        or 0
    )
    total_cost = (
        db.scalar(
            select(func.coalesce(func.sum(PromptHistory.estimated_cost_usd), 0)).where(
                *ph_filters
            )
        )
        or Decimal("0")
    )
    avg_latency = db.scalar(
        select(func.avg(PromptHistory.latency_ms)).where(
            *ph_filters,
            PromptHistory.latency_ms.is_not(None),
        )
    )
    arena_run_count = (
        db.scalar(
            select(func.count(func.distinct(PromptHistory.arena_run_id))).where(
                *ph_filters,
                PromptHistory.arena_run_id.is_not(None),
            )
        )
        or 0
    )
    routing_count = (
        db.scalar(
            select(func.count())
            .select_from(RoutingDecision)
            .where(
                RoutingDecision.organization_id == org_id,
                RoutingDecision.created_at >= since,
            )
        )
        or 0
    )
    evaluation_count = (
        db.scalar(
            select(func.count())
            .select_from(EvaluationRun)
            .where(EvaluationRun.created_at >= since)
        )
        or 0
    )

    success_rate = (success_count / total_requests) if total_requests else 0.0

    summary = AnalyticsSummary(
        total_requests=int(total_requests),
        success_count=int(success_count),
        error_count=int(error_count),
        success_rate=round(float(success_rate), 4),
        total_tokens=int(total_tokens),
        total_estimated_cost_usd=Decimal(str(total_cost)).quantize(Decimal("0.000001")),
        avg_latency_ms=round(float(avg_latency), 2) if avg_latency is not None else None,
        arena_run_count=int(arena_run_count),
        routing_decision_count=int(routing_count),
        evaluation_count=int(evaluation_count),
    )

    day_col = cast(PromptHistory.created_at, Date).label("day")
    day_rows = db.execute(
        select(
            day_col,
            func.count().label("requests"),
            func.sum(case((PromptHistory.status == "success", 1), else_=0)).label(
                "success_count"
            ),
            func.sum(case((PromptHistory.status == "error", 1), else_=0)).label(
                "error_count"
            ),
            func.coalesce(func.sum(PromptHistory.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(PromptHistory.estimated_cost_usd), 0).label("cost"),
        )
        .where(*ph_filters)
        .group_by(day_col)
        .order_by(day_col.asc())
    ).all()

    usage_by_day = [
        UsageByDayItem(
            day=row.day,
            requests=int(row.requests or 0),
            success_count=int(row.success_count or 0),
            error_count=int(row.error_count or 0),
            tokens=int(row.tokens or 0),
            estimated_cost_usd=Decimal(str(row.cost or 0)).quantize(Decimal("0.000001")),
        )
        for row in day_rows
    ]

    provider_rows = db.execute(
        select(
            PromptHistory.provider,
            func.count().label("requests"),
            func.sum(case((PromptHistory.status == "success", 1), else_=0)).label(
                "success_count"
            ),
            func.sum(case((PromptHistory.status == "error", 1), else_=0)).label(
                "error_count"
            ),
            func.coalesce(func.sum(PromptHistory.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(PromptHistory.estimated_cost_usd), 0).label("cost"),
            func.avg(PromptHistory.latency_ms).label("avg_latency"),
        )
        .where(*ph_filters)
        .group_by(PromptHistory.provider)
        .order_by(func.count().desc())
    ).all()

    usage_by_provider: list[UsageByProviderItem] = []
    for row in provider_rows:
        reqs = int(row.requests or 0)
        succ = int(row.success_count or 0)
        usage_by_provider.append(
            UsageByProviderItem(
                provider=row.provider,
                requests=reqs,
                success_count=succ,
                error_count=int(row.error_count or 0),
                success_rate=round((succ / reqs) if reqs else 0.0, 4),
                tokens=int(row.tokens or 0),
                estimated_cost_usd=Decimal(str(row.cost or 0)).quantize(
                    Decimal("0.000001")
                ),
                avg_latency_ms=(
                    round(float(row.avg_latency), 2)
                    if row.avg_latency is not None
                    else None
                ),
            )
        )

    model_rows = db.execute(
        select(
            PromptHistory.provider,
            PromptHistory.model,
            func.count().label("requests"),
            func.coalesce(func.sum(PromptHistory.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(PromptHistory.estimated_cost_usd), 0).label("cost"),
            func.avg(PromptHistory.latency_ms).label("avg_latency"),
        )
        .where(*ph_filters)
        .group_by(PromptHistory.provider, PromptHistory.model)
        .order_by(func.count().desc())
        .limit(10)
    ).all()

    usage_by_model = [
        UsageByModelItem(
            provider=row.provider,
            model=row.model,
            requests=int(row.requests or 0),
            tokens=int(row.tokens or 0),
            estimated_cost_usd=Decimal(str(row.cost or 0)).quantize(Decimal("0.000001")),
            avg_latency_ms=(
                round(float(row.avg_latency), 2) if row.avg_latency is not None else None
            ),
        )
        for row in model_rows
    ]

    status_rows = db.execute(
        select(PromptHistory.status, func.count().label("count"))
        .where(*ph_filters)
        .group_by(PromptHistory.status)
        .order_by(func.count().desc())
    ).all()
    status_breakdown = [
        StatusBreakdownItem(status=row.status, count=int(row.count or 0))
        for row in status_rows
    ]

    routing_rows = db.execute(
        select(RoutingDecision.task_type, func.count().label("count"))
        .where(
            RoutingDecision.organization_id == org_id,
            RoutingDecision.created_at >= since,
        )
        .group_by(RoutingDecision.task_type)
        .order_by(func.count().desc())
    ).all()
    routing_by_task_type = [
        RoutingByTaskItem(task_type=row.task_type, count=int(row.count or 0))
        for row in routing_rows
    ]

    return AnalyticsOverviewResponse(
        organization_slug=organization_slug,
        days=days,
        summary=summary,
        usage_by_day=usage_by_day,
        usage_by_provider=usage_by_provider,
        usage_by_model=usage_by_model,
        status_breakdown=status_breakdown,
        routing_by_task_type=routing_by_task_type,
    )
