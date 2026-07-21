"""
Password hashing and JWT helpers.

Why this exists:
- Centralizes crypto so routes never invent ad-hoc token/password logic.
- Access JWTs stay short-lived; opaque refresh tokens live in Postgres.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True when plaintext matches the stored hash."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_token(raw: str) -> str:
    """SHA-256 hex digest for opaque tokens (invites, refresh)."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_access_token(
    *,
    subject: str | UUID,
    expires_minutes: int | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT access token."""
    settings = get_settings()
    expire_delta = timedelta(
        minutes=expires_minutes
        if expires_minutes is not None
        else settings.access_token_expire_minutes
    )
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": now + expire_delta,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate an access token.

    Raises JWTError when the token is invalid or expired.
    """
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    if payload.get("type") != "access":
        raise JWTError("Invalid token type")
    return payload


def mint_opaque_token(prefix: str, nbytes: int = 32) -> str:
    """Create a high-entropy opaque token with a stable prefix."""
    return f"{prefix}{secrets.token_urlsafe(nbytes)}"
