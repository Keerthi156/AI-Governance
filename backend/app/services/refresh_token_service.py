"""
Refresh-token service — issue, rotate, and revoke opaque session tokens.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.core.security import hash_token, mint_opaque_token
from app.models.refresh_token import RefreshToken
from app.models.user import User


def issue_refresh_token(db: Session, user: User) -> tuple[str, int]:
    """
    Persist a new refresh token for the user.

    Returns (plaintext_token, expires_in_seconds).
    """
    settings = get_settings()
    raw = mint_opaque_token("agr_")
    expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    row = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        expires_at=expires,
    )
    db.add(row)
    db.commit()
    return raw, settings.refresh_token_expire_days * 24 * 60 * 60


def rotate_refresh_token(db: Session, raw_token: str) -> tuple[User, str, int]:
    """
    Validate a refresh token, revoke it, and issue a replacement.

    Returns (user, new_plaintext_refresh, expires_in_seconds).
    """
    from app.services.auth_service import get_user_by_id

    cleaned = raw_token.strip()
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(cleaned))
    )
    if row is None:
        raise UnauthorizedError("Invalid refresh token")
    now = datetime.now(timezone.utc)
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if row.revoked_at is not None or expires < now:
        raise UnauthorizedError("Refresh token expired or revoked")

    user = get_user_by_id(db, row.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Account is inactive")

    new_raw, expires_in = issue_refresh_token(db, user)
    # Re-load old row after issue (new session state) and mark revoked + replaced.
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(cleaned))
    )
    if row is not None:
        replacement = db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(new_raw))
        )
        row.revoked_at = datetime.now(timezone.utc)
        if replacement is not None:
            row.replaced_by_id = replacement.id
        db.add(row)
        db.commit()

    return user, new_raw, expires_in


def revoke_refresh_token(db: Session, raw_token: str | None) -> None:
    if not raw_token or not raw_token.strip():
        return
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token.strip()))
    )
    if row is None:
        return
    if row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.add(row)
        db.commit()


def revoke_all_refresh_tokens(db: Session, user_id) -> None:
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    ).all()
    for row in rows:
        row.revoked_at = now
        db.add(row)
    db.commit()
