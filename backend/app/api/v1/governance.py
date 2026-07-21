"""
Governance policy HTTP routes.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.schemas.governance import (
    PolicyCreateRequest,
    PolicyEvaluateRequest,
    PolicyEvaluateResponse,
    PolicyResponse,
    PolicyUpdateRequest,
)
from app.services.audit_service import record_event
from app.services.governance_service import (
    create_policy,
    delete_policy,
    dry_run_evaluate,
    list_policies,
    update_policy,
)

router = APIRouter(prefix="/governance", tags=["governance"])


@router.get("/policies", response_model=list[PolicyResponse])
def get_policies(
    organization_slug: str = Query(default="default"),
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("governance:read")),
) -> list[PolicyResponse]:
    """List governance policies for an organization."""
    return list_policies(
        db,
        organization_slug=organization_slug,
        active_only=active_only,
    )


@router.post("/policies", response_model=PolicyResponse, status_code=201)
def post_policy(
    body: PolicyCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance:manage")),
) -> PolicyResponse:
    """Create a governance policy."""
    created = create_policy(db, body)
    record_event(
        action="governance.policy.create",
        status="success",
        actor=current_user,
        resource_type="governance_policy",
        resource_id=str(created.id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Created policy {created.name}",
        details={"name": created.name, "is_active": created.is_active},
    )
    return created


@router.patch("/policies/{policy_id}", response_model=PolicyResponse)
def patch_policy(
    policy_id: UUID,
    body: PolicyUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance:manage")),
) -> PolicyResponse:
    """Update a governance policy."""
    updated = update_policy(db, policy_id, body)
    record_event(
        action="governance.policy.update",
        status="success",
        actor=current_user,
        resource_type="governance_policy",
        resource_id=str(updated.id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Updated policy {updated.name}",
        details=body.model_dump(exclude_none=True),
    )
    return updated


@router.delete("/policies/{policy_id}", status_code=204)
def remove_policy(
    policy_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance:manage")),
) -> None:
    """Delete a governance policy."""
    delete_policy(db, policy_id)
    record_event(
        action="governance.policy.delete",
        status="success",
        actor=current_user,
        resource_type="governance_policy",
        resource_id=str(policy_id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Deleted policy {policy_id}",
    )


@router.post("/evaluate", response_model=PolicyEvaluateResponse)
def evaluate_policy(
    body: PolicyEvaluateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("governance:read")),
) -> PolicyEvaluateResponse:
    """Dry-run policy evaluation without calling an LLM."""
    return dry_run_evaluate(
        db,
        organization_slug=body.organization_slug,
        provider=body.provider,
        model=body.model,
        prompt=body.prompt,
        max_tokens=body.max_tokens,
    )
