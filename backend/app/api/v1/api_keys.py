"""
API key HTTP routes — create, list, and revoke service-account credentials.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.schemas.api_key import ApiKeyCreatedResponse, ApiKeyCreateRequest, ApiKeyResponse
from app.services.api_key_service import create_api_key, list_api_keys, revoke_api_key
from app.services.audit_service import record_event

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.get("", response_model=list[ApiKeyResponse])
def get_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("api_keys:manage")),
) -> list[ApiKeyResponse]:
    """List API keys owned by the current user."""
    return list_api_keys(db, owner=current_user)


@router.post("", response_model=ApiKeyCreatedResponse, status_code=201)
def post_api_key(
    body: ApiKeyCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("api_keys:manage")),
) -> ApiKeyCreatedResponse:
    """Create an API key. The full secret is returned only in this response."""
    created = create_api_key(db, owner=current_user, body=body)
    record_event(
        action="api_keys.create",
        status="success",
        actor=current_user,
        resource_type="api_key",
        resource_id=str(created.id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Created API key “{created.name}” ({created.key_prefix}…)",
        details={
            "key_prefix": created.key_prefix,
            "role": created.role,
            "organization_slug": created.organization_slug,
        },
    )
    return created


@router.delete("/{key_id}", response_model=ApiKeyResponse)
def delete_api_key(
    key_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("api_keys:manage")),
) -> ApiKeyResponse:
    """Revoke an API key owned by the current user."""
    revoked = revoke_api_key(db, owner=current_user, key_id=key_id)
    record_event(
        action="api_keys.revoke",
        status="success",
        actor=current_user,
        resource_type="api_key",
        resource_id=str(revoked.id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Revoked API key “{revoked.name}” ({revoked.key_prefix}…)",
        details={"key_prefix": revoked.key_prefix},
    )
    return revoked
