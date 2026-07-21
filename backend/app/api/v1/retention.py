"""
Data retention HTTP routes — settings, purge, and scheduler status.
"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.schemas.retention import (
    RetentionPurgeRequest,
    RetentionPurgeResponse,
    RetentionSchedulerStatusResponse,
    RetentionSettingsResponse,
    RetentionSettingsUpdate,
)
from app.services.audit_service import record_event
from app.services.retention_scheduler import get_scheduler_state
from app.services.retention_service import (
    get_retention_settings,
    purge_expired_records,
    update_retention_settings,
)

router = APIRouter(prefix="/retention", tags=["retention"])


@router.get("/scheduler", response_model=RetentionSchedulerStatusResponse)
def get_retention_scheduler(
    current_user: User = Depends(require_permission("retention:manage")),
) -> RetentionSchedulerStatusResponse:
    """Return platform retention scheduler status (daemon + last cycle)."""
    snap = get_scheduler_state().snapshot()
    return RetentionSchedulerStatusResponse(**snap)


@router.get("", response_model=RetentionSettingsResponse)
def get_retention(
    organization_slug: str = Query(default="default"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("retention:manage")),
) -> RetentionSettingsResponse:
    """Return retention settings and expired-row counts for an organization."""
    return get_retention_settings(
        db, actor=current_user, organization_slug=organization_slug
    )


@router.put("", response_model=RetentionSettingsResponse)
def put_retention(
    body: RetentionSettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("retention:manage")),
) -> RetentionSettingsResponse:
    """Update retention windows and optional auto-purge enrollment."""
    updated = update_retention_settings(db, actor=current_user, body=body)
    record_event(
        action="retention.update",
        status="success",
        actor=current_user,
        organization_id=updated.organization_id,
        resource_type="organization",
        resource_id=str(updated.organization_id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Updated retention for {updated.organization_slug}",
        details={
            "prompt_history_retention_days": updated.prompt_history_retention_days,
            "audit_events_retention_days": updated.audit_events_retention_days,
            "retention_auto_purge_enabled": updated.retention_auto_purge_enabled,
        },
    )
    return updated


@router.post("/purge", response_model=RetentionPurgeResponse)
def post_retention_purge(
    body: RetentionPurgeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("retention:manage")),
) -> RetentionPurgeResponse:
    """Delete (or dry-run count) rows older than configured retention windows."""
    result = purge_expired_records(
        db,
        actor=current_user,
        organization_slug=body.organization_slug,
        dry_run=body.dry_run,
    )
    record_event(
        action="retention.purge",
        status="success",
        actor=current_user,
        resource_type="organization",
        request_id=getattr(request.state, "request_id", None),
        summary=(
            f"{'Dry-run purge' if result.dry_run else 'Purged'} "
            f"{result.organization_slug}: "
            f"history={result.prompt_history_deleted} audit={result.audit_events_deleted}"
        ),
        details=result.model_dump(mode="json"),
    )
    return result
