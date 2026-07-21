"""
FastAPI dependencies for authentication and RBAC.

Why this exists:
- Routes declare `Depends(get_current_user)` / `Depends(require_permission(...))`.
- Supports JWT access tokens and platform API keys (Bearer agk_…).
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.rbac import role_has_permission
from app.core.security import decode_access_token
from app.models.user import User
from app.services.auth_service import get_user_by_id

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from a Bearer JWT or API key."""
    from app.services.api_key_service import (
        authenticate_api_key,
        bind_api_key_context,
        clear_api_key_context,
    )
    from app.services.organization_service import bind_request_actor

    clear_api_key_context()

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("Missing or invalid Authorization header")

    token = credentials.credentials.strip()

    # Platform API keys start with agk_
    if token.startswith("agk_"):
        user, api_key = authenticate_api_key(db, token)
        bind_api_key_context(role=api_key.role, organization_id=api_key.organization_id)
        bind_request_actor(user)
        return user

    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if not subject:
            raise UnauthorizedError("Invalid access token")
        user_id = UUID(str(subject))
    except (JWTError, ValueError, TypeError) as exc:
        raise UnauthorizedError("Invalid or expired access token") from exc

    user = get_user_by_id(db, user_id)
    if user is None:
        raise UnauthorizedError("User not found")
    if not user.is_active:
        raise UnauthorizedError("Account is inactive")
    bind_request_actor(user)
    return user


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Return the authenticated user when a Bearer token is present; else None."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    try:
        return get_current_user(credentials=credentials, db=db)
    except UnauthorizedError:
        return None


def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    """Alias kept for clarity at call sites; get_current_user already checks is_active."""
    return user


def require_roles(*allowed_roles: str) -> Callable[..., User]:
    """Dependency factory: require the caller to have one of the listed roles."""

    def _dependency(user: User = Depends(get_current_user)) -> User:
        from app.services.api_key_service import get_effective_role

        role = get_effective_role(user)
        if role not in allowed_roles:
            raise ForbiddenError(
                f"Requires one of roles: {', '.join(allowed_roles)} (you are {role})"
            )
        return user

    return _dependency


def require_permission(permission: str) -> Callable[..., User]:
    """Dependency factory: require a named permission derived from the caller's role."""

    def _dependency(user: User = Depends(get_current_user)) -> User:
        from app.services.api_key_service import get_effective_role

        role = get_effective_role(user)
        if not role_has_permission(role, permission):
            raise ForbiddenError(
                f"Missing permission '{permission}' for role '{role}'"
            )
        return user

    return _dependency
