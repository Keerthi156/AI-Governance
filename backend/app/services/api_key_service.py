"""
API key service — create, list, revoke, and authenticate.

Why this exists:
- Service accounts for CI/CD and backend integrations without user passwords.
- SHA-256 hashes at rest; plaintext returned only on create.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from contextvars import ContextVar
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ForbiddenError, NotFoundError, UnauthorizedError, ValidationAppError
from app.core.rbac import ROLE_RANK, is_valid_role
from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas.api_key import ApiKeyCreatedResponse, ApiKeyCreateRequest, ApiKeyResponse
from app.services.organization_service import (
    require_organization_access,
    user_is_org_member,
)

API_KEY_PREFIX = "agk_"
_PREFIX_LEN = 16  # includes "agk_" + 12 hex chars from token

_effective_role: ContextVar[str | None] = ContextVar("api_key_effective_role", default=None)
_api_key_org_id: ContextVar[UUID | None] = ContextVar("api_key_org_id", default=None)


def bind_api_key_context(*, role: str, organization_id: UUID) -> None:
    _effective_role.set(role)
    _api_key_org_id.set(organization_id)


def clear_api_key_context() -> None:
    _effective_role.set(None)
    _api_key_org_id.set(None)


def get_effective_role(user: User) -> str:
    """Role used for RBAC — API key role when authenticated via key."""
    override = _effective_role.get()
    return override if override else user.role


def get_api_key_organization_id() -> UUID | None:
    return _api_key_org_id.get()


def _hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _generate_plaintext() -> tuple[str, str]:
    """Return (plaintext, key_prefix). Prefix is first 16 chars for indexed lookup."""
    raw = secrets.token_hex(24)  # 48 hex chars
    plaintext = f"{API_KEY_PREFIX}{raw}"
    return plaintext, plaintext[:_PREFIX_LEN]


def _is_active(row: ApiKey, *, now: datetime | None = None) -> bool:
    current = now or datetime.now(timezone.utc)
    if row.revoked_at is not None:
        return False
    if row.expires_at is not None:
        expires = row.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= current:
            return False
    return True


def api_key_to_response(row: ApiKey) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=row.id,
        name=row.name,
        key_prefix=row.key_prefix,
        role=row.role,
        organization_id=row.organization_id,
        organization_slug=row.organization.slug,
        user_id=row.user_id,
        last_used_at=row.last_used_at,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        notes=row.notes,
        created_at=row.created_at,
        is_active=_is_active(row),
    )


def list_api_keys(db: Session, *, owner: User) -> list[ApiKeyResponse]:
    rows = db.scalars(
        select(ApiKey)
        .options(joinedload(ApiKey.organization))
        .where(ApiKey.user_id == owner.id)
        .order_by(ApiKey.created_at.desc())
    ).all()
    return [api_key_to_response(row) for row in rows]


def create_api_key(
    db: Session,
    *,
    owner: User,
    body: ApiKeyCreateRequest,
) -> ApiKeyCreatedResponse:
    if not is_valid_role(body.role):
        raise ValidationAppError(f"Invalid role '{body.role}'")
    if ROLE_RANK.get(body.role, 0) > ROLE_RANK.get(owner.role, 0):
        raise ForbiddenError(
            f"Cannot create an API key with role '{body.role}' "
            f"(your role is '{owner.role}')"
        )

    org = require_organization_access(db, body.organization_slug, actor=owner)
    if not user_is_org_member(db, user_id=owner.id, organization_id=org.id):
        raise ForbiddenError("You must be a member of the organization to create a key")

    if body.expires_at is not None:
        expires = body.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            raise ValidationAppError("expires_at must be in the future")

    plaintext, prefix = _generate_plaintext()
    row = ApiKey(
        user_id=owner.id,
        organization_id=org.id,
        name=body.name.strip(),
        key_prefix=prefix,
        key_hash=_hash_key(plaintext),
        role=body.role,
        expires_at=body.expires_at,
        notes=body.notes.strip() if body.notes else None,
    )
    db.add(row)
    db.commit()
    row = db.scalar(
        select(ApiKey)
        .options(joinedload(ApiKey.organization))
        .where(ApiKey.id == row.id)
    )
    assert row is not None
    base = api_key_to_response(row)
    return ApiKeyCreatedResponse(**base.model_dump(), api_key=plaintext)


def revoke_api_key(db: Session, *, owner: User, key_id: UUID) -> ApiKeyResponse:
    row = db.scalar(
        select(ApiKey)
        .options(joinedload(ApiKey.organization))
        .where(ApiKey.id == key_id, ApiKey.user_id == owner.id)
    )
    if row is None:
        raise NotFoundError("API key not found")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.add(row)
        db.commit()
        db.refresh(row)
        row = db.scalar(
            select(ApiKey)
            .options(joinedload(ApiKey.organization))
            .where(ApiKey.id == key_id)
        )
        assert row is not None
    return api_key_to_response(row)


def authenticate_api_key(db: Session, plaintext: str) -> tuple[User, ApiKey]:
    """Validate a Bearer API key and return (owner user, key row)."""
    if not plaintext.startswith(API_KEY_PREFIX) or len(plaintext) < _PREFIX_LEN + 8:
        raise UnauthorizedError("Invalid API key")

    prefix = plaintext[:_PREFIX_LEN]
    row = db.scalar(
        select(ApiKey)
        .options(
            joinedload(ApiKey.user).joinedload(User.organization),
            joinedload(ApiKey.organization),
        )
        .where(ApiKey.key_prefix == prefix)
    )
    if row is None:
        raise UnauthorizedError("Invalid API key")
    if not hmac.compare_digest(row.key_hash, _hash_key(plaintext)):
        raise UnauthorizedError("Invalid API key")
    if not _is_active(row):
        raise UnauthorizedError("API key is revoked or expired")

    user = row.user
    if user is None or not user.is_active:
        raise UnauthorizedError("API key owner is inactive")

    row.last_used_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()

    return user, row
