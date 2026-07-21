"""
Prompt history HTTP routes.

Why this exists:
- Exposes audit-friendly list/detail/arena grouping for the UI and later analytics.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.schemas.history import ArenaHistoryResponse, HistoryItem, HistoryListResponse
from app.services.history_service import (
    get_arena_history,
    get_prompt_history_item,
    list_prompt_history,
)

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=HistoryListResponse)
def list_history(
    organization_slug: str = Query(default="default"),
    provider: str | None = Query(default=None),
    status: str | None = Query(default=None, pattern="^(pending|success|error)$"),
    arena_run_id: UUID | None = Query(default=None),
    arena_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("history:read")),
) -> HistoryListResponse:
    """List prompt history with optional filters and pagination."""
    return list_prompt_history(
        db,
        organization_slug=organization_slug,
        provider=provider,
        status=status,
        arena_run_id=arena_run_id,
        arena_only=arena_only,
        page=page,
        page_size=page_size,
    )


@router.get("/arena/{arena_run_id}", response_model=ArenaHistoryResponse)
def get_arena_run_history(
    arena_run_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("history:read")),
) -> ArenaHistoryResponse:
    """Fetch all participant results for one arena run."""
    return get_arena_history(db, arena_run_id)


@router.get("/{history_id}", response_model=HistoryItem)
def get_history_item(
    history_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("history:read")),
) -> HistoryItem:
    """Fetch a single prompt history record."""
    return get_prompt_history_item(db, history_id)
