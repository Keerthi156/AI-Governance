"""
BYOK provider credential HTTP routes.
"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.schemas.provider_credential import (
    ProviderCredentialResponse,
    ProviderCredentialUpsert,
)
from app.services.audit_service import record_event
from app.services.provider_credential_service import (
    delete_provider_credential,
    list_provider_credentials,
    upsert_provider_credential,
)

router = APIRouter(prefix="/credentials", tags=["credentials"])


@router.get("", response_model=list[ProviderCredentialResponse])
def get_credentials(
    organization_slug: str = Query(default="default"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("credentials:read")),
) -> list[ProviderCredentialResponse]:
    """List provider credential status for an organization (no secrets)."""
    return list_provider_credentials(
        db, actor=current_user, organization_slug=organization_slug
    )


@router.put("/{provider}", response_model=ProviderCredentialResponse)
def put_credential(
    provider: str,
    body: ProviderCredentialUpsert,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("credentials:manage")),
) -> ProviderCredentialResponse:
    """Create or replace an encrypted org provider API key."""
    saved = upsert_provider_credential(
        db, actor=current_user, provider=provider, body=body
    )
    record_event(
        action="credentials.upsert",
        status="success",
        actor=current_user,
        resource_type="provider_credential",
        resource_id=str(saved.id) if saved.id else None,
        request_id=getattr(request.state, "request_id", None),
        summary=f"Upserted {saved.provider} credential for {saved.organization_slug}",
        details={
            "provider": saved.provider,
            "organization_slug": saved.organization_slug,
            "key_hint": saved.key_hint,
        },
    )
    return saved


@router.delete("/{provider}", response_model=ProviderCredentialResponse)
def remove_credential(
    provider: str,
    request: Request,
    organization_slug: str = Query(default="default"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("credentials:manage")),
) -> ProviderCredentialResponse:
    """Delete org BYOK credential (falls back to platform env key)."""
    removed = delete_provider_credential(
        db,
        actor=current_user,
        provider=provider,
        organization_slug=organization_slug,
    )
    record_event(
        action="credentials.delete",
        status="success",
        actor=current_user,
        resource_type="provider_credential",
        request_id=getattr(request.state, "request_id", None),
        summary=f"Deleted {removed.provider} credential for {removed.organization_slug}",
        details={
            "provider": removed.provider,
            "organization_slug": removed.organization_slug,
            "fallback": removed.source,
        },
    )
    return removed
