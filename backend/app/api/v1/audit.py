"""
Audit log HTTP routes.
"""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.schemas.audit import AuditActionCatalogResponse, AuditEventListResponse
from app.services.audit_service import (
    EXPORT_MAX_ROWS,
    KNOWN_ACTIONS,
    export_audit_events,
    list_audit_events,
    record_event,
    render_audit_export_csv,
    render_audit_export_json,
)

router = APIRouter(prefix="/audit", tags=["audit"])


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.get("/actions", response_model=AuditActionCatalogResponse)
def audit_actions(
    _: User = Depends(require_permission("audit:read")),
) -> AuditActionCatalogResponse:
    """Return known audit action codes for UI filters."""
    return AuditActionCatalogResponse(actions=list(KNOWN_ACTIONS))


@router.get("/events/export")
def export_audit_events_route(
    request: Request,
    format: str = Query(default="csv", pattern="^(csv|json)$"),
    action: str | None = Query(default=None),
    status: str | None = Query(default=None, pattern="^(success|failure|denied)$"),
    limit: int = Query(default=EXPORT_MAX_ROWS, ge=1, le=EXPORT_MAX_ROWS),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("audit:read")),
) -> Response:
    """Download filtered audit events as CSV or JSON (compliance export)."""
    items = export_audit_events(
        db,
        organization_id=current_user.organization_id,
        action=action,
        status=status,
        limit=limit,
    )
    if format == "json":
        body = render_audit_export_json(items)
        media_type = "application/json"
        filename = "audit-events.json"
    else:
        body = render_audit_export_csv(items)
        media_type = "text/csv; charset=utf-8"
        filename = "audit-events.csv"

    record_event(
        action="audit.export",
        status="success",
        actor=current_user,
        resource_type="audit_export",
        request_id=_request_id(request),
        summary=f"Exported {len(items)} audit events as {format}",
        details={
            "format": format,
            "count": len(items),
            "action_filter": action,
            "status_filter": status,
            "limit": limit,
        },
    )

    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/events", response_model=AuditEventListResponse)
def get_audit_events(
    request: Request,
    action: str | None = Query(default=None),
    status: str | None = Query(default=None, pattern="^(success|failure|denied)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("audit:read")),
) -> AuditEventListResponse:
    """List audit events for the caller's organization."""
    _ = _request_id(request)  # available for future correlation filters
    return list_audit_events(
        db,
        organization_id=current_user.organization_id,
        action=action,
        status=status,
        page=page,
        page_size=page_size,
    )
