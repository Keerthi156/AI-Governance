"""
Admin / RBAC HTTP routes.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.rbac import PERMISSION_ROLES, permissions_for_role
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.rbac import RoleCatalogResponse, UpdateUserRequest
from app.services.audit_service import record_event
from app.services.rbac_service import list_organization_users, update_organization_user

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/roles", response_model=RoleCatalogResponse)
def role_catalog(
    _: User = Depends(require_permission("users:manage")),
) -> RoleCatalogResponse:
    """Return the role → permission matrix for admin UIs."""
    matrix = {
        role: permissions_for_role(role)
        for role in ("viewer", "member", "admin")
    }
    return RoleCatalogResponse(
        matrix=matrix,
        permissions=sorted(PERMISSION_ROLES.keys()),
    )


@router.get("/users", response_model=list[UserResponse])
def list_users(
    current_user: User = Depends(require_permission("users:manage")),
    db: Session = Depends(get_db),
) -> list[UserResponse]:
    """List users in the caller's organization."""
    return list_organization_users(db, actor=current_user)


@router.patch("/users/{user_id}", response_model=UserResponse)
def patch_user(
    user_id: UUID,
    body: UpdateUserRequest,
    request: Request,
    current_user: User = Depends(require_permission("users:manage")),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Update a user's role or active flag within the caller's organization."""
    updated = update_organization_user(
        db,
        actor=current_user,
        user_id=user_id,
        body=body,
    )
    record_event(
        action="users.update",
        status="success",
        actor=current_user,
        resource_type="user",
        resource_id=str(updated.id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Updated user {updated.email}",
        details={
            "role": updated.role,
            "is_active": updated.is_active,
            "changes": body.model_dump(exclude_none=True),
        },
    )
    return updated
