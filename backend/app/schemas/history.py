"""Prompt history response schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class HistoryItem(BaseModel):
    """One prompt_history row for list/detail views."""

    id: UUID
    organization_slug: str
    provider: str
    model: str
    prompt: str
    response: str | None
    status: str
    error_message: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: Decimal | None = None
    latency_ms: int | None = None
    arena_run_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class HistoryListResponse(BaseModel):
    """Paginated prompt history list."""

    items: list[HistoryItem]
    total: int
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    pages: int = Field(..., ge=0)


class ArenaHistoryResponse(BaseModel):
    """All history rows for a single arena run."""

    arena_run_id: UUID
    organization_slug: str
    prompt: str
    items: list[HistoryItem]
    success_count: int
    error_count: int
    total_estimated_cost_usd: Decimal | None
