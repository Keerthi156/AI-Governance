"""
Audit webhook HTTP routes.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.schemas.webhook import (
    WebhookCreateRequest,
    WebhookDeliveryListResponse,
    WebhookResponse,
    WebhookUpdateRequest,
)
from app.services.audit_service import record_event
from app.services.webhook_service import (
    create_webhook,
    delete_webhook,
    list_deliveries,
    list_webhooks,
    test_webhook,
    update_webhook,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/deliveries", response_model=WebhookDeliveryListResponse)
def get_webhook_deliveries(
    organization_slug: str = Query(default="default"),
    webhook_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("webhooks:manage")),
) -> WebhookDeliveryListResponse:
    """List recent webhook delivery attempts (history + pending retries)."""
    return list_deliveries(
        db,
        actor=current_user,
        organization_slug=organization_slug,
        webhook_id=webhook_id,
        limit=limit,
    )


@router.get("", response_model=list[WebhookResponse])
def get_webhooks(
    organization_slug: str = Query(default="default"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("webhooks:manage")),
) -> list[WebhookResponse]:
    """List audit webhooks for an organization."""
    return list_webhooks(db, actor=current_user, organization_slug=organization_slug)


@router.post("", response_model=WebhookResponse, status_code=201)
def post_webhook(
    body: WebhookCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("webhooks:manage")),
) -> WebhookResponse:
    """Create an audit webhook endpoint."""
    created = create_webhook(db, actor=current_user, body=body)
    record_event(
        action="webhooks.create",
        status="success",
        actor=current_user,
        resource_type="audit_webhook",
        resource_id=str(created.id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Created webhook “{created.name}”",
        details={"url": created.url, "organization_slug": created.organization_slug},
    )
    return created


@router.patch("/{webhook_id}", response_model=WebhookResponse)
def patch_webhook(
    webhook_id: UUID,
    body: WebhookUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("webhooks:manage")),
) -> WebhookResponse:
    """Update an audit webhook."""
    updated = update_webhook(db, actor=current_user, webhook_id=webhook_id, body=body)
    record_event(
        action="webhooks.update",
        status="success",
        actor=current_user,
        resource_type="audit_webhook",
        resource_id=str(updated.id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Updated webhook “{updated.name}”",
        details={"is_active": updated.is_active},
    )
    return updated


@router.delete("/{webhook_id}", status_code=204)
def remove_webhook(
    webhook_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("webhooks:manage")),
) -> None:
    """Delete an audit webhook."""
    delete_webhook(db, actor=current_user, webhook_id=webhook_id)
    record_event(
        action="webhooks.delete",
        status="success",
        actor=current_user,
        resource_type="audit_webhook",
        resource_id=str(webhook_id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Deleted webhook {webhook_id}",
    )


@router.post("/{webhook_id}/test", response_model=WebhookResponse)
def post_webhook_test(
    webhook_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("webhooks:manage")),
) -> WebhookResponse:
    """Send a test payload and return updated delivery status."""
    return test_webhook(db, actor=current_user, webhook_id=webhook_id)
