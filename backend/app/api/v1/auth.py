"""
Authentication HTTP routes.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_optional_current_user
from app.core.exceptions import UnauthorizedError
from app.models.user import User
from app.schemas.auth import (
    InviteAcceptRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.audit_service import record_event
from app.services.auth_service import (
    accept_invite_and_issue,
    authenticate_user,
    logout_session,
    refresh_session,
    register_user,
    user_to_response,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(
    body: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Create an account and return access + refresh tokens."""
    result = register_user(db, body)
    record_event(
        action="auth.register",
        status="success",
        organization_id=result.user.organization_id,
        actor_email=result.user.email,
        resource_type="user",
        resource_id=str(result.user.id),
        request_id=_request_id(request),
        summary=f"Registered {result.user.email} as {result.user.role}",
        details={
            "role": result.user.role,
            "organization_slug": result.user.organization_slug,
            "via_invite": bool(body.invite_token),
        },
    )
    return result


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Exchange email/password for access + refresh tokens."""
    try:
        result = authenticate_user(db, body)
    except UnauthorizedError:
        record_event(
            action="auth.login_failed",
            status="failure",
            actor_email=str(body.email),
            resource_type="user",
            request_id=_request_id(request),
            summary=f"Failed login for {body.email}",
        )
        raise
    record_event(
        action="auth.login",
        status="success",
        organization_id=result.user.organization_id,
        actor_email=result.user.email,
        resource_type="user",
        resource_id=str(result.user.id),
        request_id=_request_id(request),
        summary=f"Login {result.user.email}",
        details={"role": result.user.role},
    )
    return result


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    body: RefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Rotate refresh token and issue a new access token."""
    try:
        result = refresh_session(db, body.refresh_token)
    except UnauthorizedError:
        record_event(
            action="auth.refresh_failed",
            status="failure",
            resource_type="user",
            request_id=_request_id(request),
            summary="Refresh token rejected",
        )
        raise
    record_event(
        action="auth.refresh",
        status="success",
        organization_id=result.user.organization_id,
        actor_email=result.user.email,
        resource_type="user",
        resource_id=str(result.user.id),
        request_id=_request_id(request),
        summary=f"Refreshed session for {result.user.email}",
    )
    return result


@router.post("/logout", status_code=204)
def logout(
    body: LogoutRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    """Revoke a refresh token (best-effort)."""
    logout_session(db, body.refresh_token)
    record_event(
        action="auth.logout",
        status="success",
        resource_type="user",
        request_id=_request_id(request),
        summary="Logout / refresh revoked",
    )


@router.post("/invites/accept", response_model=TokenResponse)
def accept_invite(
    body: InviteAcceptRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> TokenResponse:
    """Accept an organization invite (optionally creating an account)."""
    result = accept_invite_and_issue(db, body, actor=current_user)
    record_event(
        action="organizations.invite_accept",
        status="success",
        organization_id=result.user.organization_id,
        actor_email=result.user.email,
        resource_type="user",
        resource_id=str(result.user.id),
        request_id=_request_id(request),
        summary=f"Accepted invite as {result.user.email}",
    )
    return result


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the authenticated user profile (API key role when using a key)."""
    from app.core.rbac import permissions_for_role
    from app.services.api_key_service import get_effective_role

    response = user_to_response(current_user)
    role = get_effective_role(current_user)
    if role != current_user.role:
        return response.model_copy(
            update={"role": role, "permissions": permissions_for_role(role)}
        )
    return response
