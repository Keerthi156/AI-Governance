"""
Authentication service.

Why this exists:
- Register/login stay out of route handlers.
- Password hashing + org provisioning live in one place.
- Issues short-lived access JWTs plus rotatable refresh tokens.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.exceptions import AppException, ConflictError, UnauthorizedError
from app.core.rbac import permissions_for_role
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import (
    InviteAcceptRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.organization_service import (
    ensure_membership,
    get_or_create_organization,
)
from app.services.refresh_token_service import (
    issue_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
)


def user_to_response(user: User) -> UserResponse:
    """Map ORM user (+ loaded organization) to API shape."""
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        organization_id=user.organization_id,
        organization_slug=user.organization.slug,
        permissions=permissions_for_role(user.role),
        created_at=user.created_at,
    )


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(
        select(User)
        .options(joinedload(User.organization))
        .where(User.email == email.lower().strip())
    )


def get_user_by_id(db: Session, user_id) -> User | None:
    return db.scalar(
        select(User)
        .options(joinedload(User.organization))
        .where(User.id == user_id)
    )


def _org_user_count(db: Session, organization_id) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.organization_id == organization_id)
        )
        or 0
    )


def register_user(db: Session, body: RegisterRequest) -> TokenResponse:
    """Create a user in the requested org and return access + refresh tokens."""
    email = body.email.lower().strip()
    if get_user_by_email(db, email) is not None:
        raise ConflictError("An account with this email already exists")

    if len(body.password.encode("utf-8")) > 72:
        raise AppException(
            "Password cannot exceed 72 bytes (bcrypt limit)",
            code="password_too_long",
            status_code=422,
        )

    invite_token = (body.invite_token or "").strip() or None
    if invite_token:
        from app.services.invite_service import accept_invite

        user, _invite = accept_invite(
            db,
            body=InviteAcceptRequest(
                token=invite_token,
                password=body.password,
                full_name=body.full_name,
                email=email,
            ),
            actor=None,
        )
        return _issue_token(db, user)

    org_slug = body.organization_slug.strip().lower() or "default"
    org = get_or_create_organization(db, slug=org_slug)
    # First user in an empty org bootstraps as admin; everyone else is a member
    # (self-register has limited access — admin must invite for elevated roles).
    role = "admin" if _org_user_count(db, org.id) == 0 else "member"
    user = User(
        organization_id=org.id,
        email=email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name.strip() if body.full_name else None,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    ensure_membership(
        db,
        user_id=user.id,
        organization_id=org.id,
        role=role,
        commit=False,
    )
    db.commit()
    db.refresh(user)
    user = get_user_by_id(db, user.id)
    assert user is not None
    return _issue_token(db, user)


def authenticate_user(db: Session, body: LoginRequest) -> TokenResponse:
    """Validate credentials and return access + refresh tokens."""
    user = get_user_by_email(db, body.email)
    if user is None or not verify_password(body.password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password")
    if not user.is_active:
        raise UnauthorizedError("Account is inactive")
    return _issue_token(db, user)


def refresh_session(db: Session, refresh_token: str) -> TokenResponse:
    """Rotate refresh token and issue a new access token."""
    user, new_refresh, refresh_expires_in = rotate_refresh_token(db, refresh_token)
    return _issue_token(
        db,
        user,
        refresh_token=new_refresh,
        refresh_expires_in=refresh_expires_in,
    )


def logout_session(db: Session, refresh_token: str | None) -> None:
    revoke_refresh_token(db, refresh_token)


def accept_invite_and_issue(
    db: Session,
    body: InviteAcceptRequest,
    *,
    actor: User | None = None,
) -> TokenResponse:
    from app.services.invite_service import accept_invite

    user, _invite = accept_invite(db, body=body, actor=actor)
    return _issue_token(db, user)


def _issue_token(
    db: Session,
    user: User,
    *,
    refresh_token: str | None = None,
    refresh_expires_in: int | None = None,
) -> TokenResponse:
    settings = get_settings()
    access = create_access_token(
        subject=user.id,
        extra_claims={
            "email": user.email,
            "role": user.role,
            "org_id": str(user.organization_id),
        },
    )
    if refresh_token is None:
        refresh_token, refresh_expires_in = issue_refresh_token(db, user)
    return TokenResponse(
        access_token=access,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        refresh_token=refresh_token,
        refresh_expires_in=refresh_expires_in,
        user=user_to_response(user),
    )
