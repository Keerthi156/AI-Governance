"""
Prompt history query service.

Why this exists:
- Centralizes filters/pagination for audit and playground UIs.
- Keeps SQLAlchemy queries out of route handlers.
"""

from __future__ import annotations

import math
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.prompt_history import PromptHistory
from app.schemas.history import ArenaHistoryResponse, HistoryItem, HistoryListResponse
from app.services.organization_service import get_request_actor, require_organization_access


def _to_item(row: PromptHistory, organization_slug: str) -> HistoryItem:
    return HistoryItem(
        id=row.id,
        organization_slug=organization_slug,
        provider=row.provider,
        model=row.model,
        prompt=row.prompt,
        response=row.response,
        status=row.status,
        error_message=row.error_message,
        prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens,
        total_tokens=row.total_tokens,
        estimated_cost_usd=row.estimated_cost_usd,
        latency_ms=row.latency_ms,
        arena_run_id=row.arena_run_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_prompt_history(
    db: Session,
    *,
    organization_slug: str = "default",
    provider: str | None = None,
    status: str | None = None,
    arena_run_id: UUID | None = None,
    arena_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> HistoryListResponse:
    """Return a filtered, paginated prompt history list (newest first)."""
    if page < 1:
        raise ValidationAppError("page must be >= 1")
    if page_size < 1 or page_size > 100:
        raise ValidationAppError("page_size must be between 1 and 100")

    org = None
    try:
        org = require_organization_access(db, organization_slug)
    except NotFoundError:
        if get_request_actor() is not None:
            raise
        return HistoryListResponse(items=[], total=0, page=page, page_size=page_size, pages=0)

    filters = [PromptHistory.organization_id == org.id]
    if provider:
        filters.append(PromptHistory.provider == provider.strip().lower())
    if status:
        filters.append(PromptHistory.status == status.strip().lower())
    if arena_run_id is not None:
        filters.append(PromptHistory.arena_run_id == arena_run_id)
    if arena_only:
        filters.append(PromptHistory.arena_run_id.is_not(None))

    total = db.scalar(
        select(func.count()).select_from(PromptHistory).where(*filters)
    ) or 0

    rows = db.scalars(
        select(PromptHistory)
        .where(*filters)
        .order_by(PromptHistory.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    pages = math.ceil(total / page_size) if total else 0
    return HistoryListResponse(
        items=[_to_item(row, org.slug) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


def get_prompt_history_item(db: Session, history_id: UUID) -> HistoryItem:
    """Return a single history row or raise NotFoundError."""
    row = db.scalar(
        select(PromptHistory)
        .options(joinedload(PromptHistory.organization))
        .where(PromptHistory.id == history_id)
    )
    if row is None:
        raise NotFoundError(f"Prompt history '{history_id}' not found")
    return _to_item(row, row.organization.slug)


def get_arena_history(db: Session, arena_run_id: UUID) -> ArenaHistoryResponse:
    """Return all history rows for one arena run, newest grouping first."""
    rows = db.scalars(
        select(PromptHistory)
        .options(joinedload(PromptHistory.organization))
        .where(PromptHistory.arena_run_id == arena_run_id)
        .order_by(PromptHistory.created_at.asc())
    ).all()
    if not rows:
        raise NotFoundError(f"Arena run '{arena_run_id}' not found")

    org_slug = rows[0].organization.slug
    items = [_to_item(row, org_slug) for row in rows]
    success_count = sum(1 for item in items if item.status == "success")
    error_count = sum(1 for item in items if item.status == "error")

    cost_total = Decimal("0")
    cost_known = False
    for item in items:
        if item.estimated_cost_usd is not None:
            cost_total += item.estimated_cost_usd
            cost_known = True

    return ArenaHistoryResponse(
        arena_run_id=arena_run_id,
        organization_slug=org_slug,
        prompt=rows[0].prompt,
        items=items,
        success_count=success_count,
        error_count=error_count,
        total_estimated_cost_usd=cost_total if cost_known else None,
    )
