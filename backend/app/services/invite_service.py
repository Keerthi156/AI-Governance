"""
Organization invite service — create, list, revoke, accept invite tokens.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationAppError,
)
from app.core.rbac import is_valid_role
from app.core.security import hash_password, hash_token, mint_opaque_token
from app.models.invite import OrganizationInvite
from app.models.user import User
from app.schemas.auth import InviteAcceptRequest, TokenResponse
from app.schemas.organization import (
    OrganizationInviteCreate,
    OrganizationInviteResponse,
)
from app.services.organization_service import (
    _require_org_admin,
    ensure_membership,
    require_organization_access,
)


def _invite_to_response(
    row: OrganizationInvite,
    *,
    token: str | None = None,
) -> OrganizationInviteResponse:
    return OrganizationInviteResponse(
        id=row.id,
        organization_id=row.organization_id,
        organization_slug=row.organization.slug,
        email=row.email,
        role=row.role,
        token_hint=row.token_hint,
        expires_at=row.expires_at,
        accepted_at=row.accepted_at,
        revoked_at=row.revoked_at,
        created_at=row.created_at,
        token=token,
    )


def create_invite(
    db: Session,
    *,
    slug: str,
    actor: User,
    body: OrganizationInviteCreate,
) -> OrganizationInviteResponse:
    org = require_organization_access(db, slug, actor=actor)
    _require_org_admin(db, actor, org)
    if not is_valid_role(body.role):
        raise ValidationAppError(f"Invalid role '{body.role}'")

    email = body.email.strip().lower() if body.email and body.email.strip() else None
    raw = mint_opaque_token("agi_")
    row = OrganizationInvite(
        organization_id=org.id,
        email=email,
        role=body.role,
        token_hash=hash_token(raw),
        token_hint=raw[-4:],
        expires_at=datetime.now(timezone.utc) + timedelta(hours=body.expires_in_hours),
        created_by_user_id=actor.id,
    )
    db.add(row)
    db.commit()
    row = db.scalar(
        select(OrganizationInvite)
        .options(joinedload(OrganizationInvite.organization))
        .where(OrganizationInvite.id == row.id)
    )
    assert row is not None
    return _invite_to_response(row, token=raw)


def list_invites(
    db: Session,
    *,
    slug: str,
    actor: User,
) -> list[OrganizationInviteResponse]:
    org = require_organization_access(db, slug, actor=actor)
    _require_org_admin(db, actor, org)
    rows = db.scalars(
        select(OrganizationInvite)
        .options(joinedload(OrganizationInvite.organization))
        .where(OrganizationInvite.organization_id == org.id)
        .order_by(OrganizationInvite.created_at.desc())
    ).all()
    return [_invite_to_response(row) for row in rows]


def revoke_invite(
    db: Session,
    *,
    slug: str,
    actor: User,
    invite_id: UUID,
) -> None:
    org = require_organization_access(db, slug, actor=actor)
    _require_org_admin(db, actor, org)
    row = db.scalar(
        select(OrganizationInvite).where(
            OrganizationInvite.id == invite_id,
            OrganizationInvite.organization_id == org.id,
        )
    )
    if row is None:
        raise NotFoundError("Invite not found")
    if row.accepted_at is not None:
        raise ValidationAppError("Invite already accepted")
    row.revoked_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()


def get_invite_by_token(db: Session, token: str) -> OrganizationInvite | None:
    cleaned = token.strip()
    if not cleaned:
        return None
    return db.scalar(
        select(OrganizationInvite)
        .options(joinedload(OrganizationInvite.organization))
        .where(OrganizationInvite.token_hash == hash_token(cleaned))
    )


def _assert_invite_usable(invite: OrganizationInvite) -> None:
    now = datetime.now(timezone.utc)
    if invite.revoked_at is not None:
        raise ValidationAppError("Invite has been revoked")
    if invite.accepted_at is not None:
        raise ValidationAppError("Invite has already been accepted")
    expires = invite.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now:
        raise ValidationAppError("Invite has expired")


def accept_invite(
    db: Session,
    *,
    body: InviteAcceptRequest,
    actor: User | None = None,
) -> tuple[User, OrganizationInvite]:
    """
    Accept an invite. Returns (user, invite).

    - Existing authenticated actor may accept (email must match when locked).
    - Existing user with password via email field.
    - New user requires password (+ email when invite is open).
    """
    from app.services.auth_service import get_user_by_email, get_user_by_id

    invite = get_invite_by_token(db, body.token)
    if invite is None:
        raise NotFoundError("Invite not found")
    _assert_invite_usable(invite)

    user: User | None = actor
    if user is None and body.email:
        user = get_user_by_email(db, str(body.email))
        if user is not None:
            if not body.password:
                raise ValidationAppError("Password required to accept invite for existing account")
            from app.core.security import verify_password

            if not verify_password(body.password, user.hashed_password):
                raise UnauthorizedError("Invalid email or password")

    if user is None and invite.email:
        user = get_user_by_email(db, invite.email)

    if user is None:
        # Create new account into the invite org.
        email = (invite.email or (str(body.email).lower().strip() if body.email else "")).strip()
        if not email:
            raise ValidationAppError("Email is required to accept this invite")
        if invite.email and email != invite.email.lower():
            raise ForbiddenError("This invite is locked to a different email")
        if not body.password:
            raise ValidationAppError("Password is required to create an account via invite")
        if get_user_by_email(db, email) is not None:
            raise ConflictError("An account with this email already exists — sign in and accept")
        if len(body.password.encode("utf-8")) > 72:
            raise ValidationAppError("Password cannot exceed 72 bytes (bcrypt limit)")
        user = User(
            organization_id=invite.organization_id,
            email=email,
            hashed_password=hash_password(body.password),
            full_name=body.full_name.strip() if body.full_name else None,
            role="member",
            is_active=True,
        )
        db.add(user)
        db.flush()
    else:
        if invite.email and user.email.lower() != invite.email.lower():
            raise ForbiddenError("This invite is locked to a different email")

    ensure_membership(
        db,
        user_id=user.id,
        organization_id=invite.organization_id,
        role=invite.role,
        commit=False,
    )
    invite.accepted_at = datetime.now(timezone.utc)
    invite.accepted_by_user_id = user.id
    db.add(invite)
    db.commit()
    user = get_user_by_id(db, user.id)
    assert user is not None
    invite = get_invite_by_token(db, body.token)
    assert invite is not None
    return user, invite
