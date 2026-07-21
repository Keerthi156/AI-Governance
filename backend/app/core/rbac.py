"""
Role-based access control (RBAC) constants and helpers.

Why this exists:
- Enterprise platforms need explicit permissions, not ad-hoc role string checks.
- Permissions are code-defined for Phase 3; a permissions table can come later.
"""

from __future__ import annotations

from typing import Final, Literal

RoleName = Literal["viewer", "member", "admin"]

ROLES: Final[tuple[RoleName, ...]] = ("viewer", "member", "admin")

ROLE_RANK: Final[dict[str, int]] = {
    "viewer": 1,
    "member": 2,
    "admin": 3,
}

# permission -> roles that grant it
PERMISSION_ROLES: Final[dict[str, frozenset[str]]] = {
    "llm:run": frozenset({"member", "admin"}),
    "arena:run": frozenset({"member", "admin"}),
    "evaluation:run": frozenset({"member", "admin"}),
    "evaluation:read": frozenset({"viewer", "member", "admin"}),
    "router:classify": frozenset({"viewer", "member", "admin"}),
    "router:route": frozenset({"member", "admin"}),
    "history:read": frozenset({"viewer", "member", "admin"}),
    "analytics:read": frozenset({"viewer", "member", "admin"}),
    "users:manage": frozenset({"admin"}),
    "governance:read": frozenset({"viewer", "member", "admin"}),
    "governance:manage": frozenset({"admin"}),
    "audit:read": frozenset({"admin"}),
    "webhooks:manage": frozenset({"admin"}),
    "retention:manage": frozenset({"admin"}),
    "compliance:read": frozenset({"admin"}),
    "rag:read": frozenset({"viewer", "member", "admin"}),
    "rag:write": frozenset({"member", "admin"}),
    "rag:query": frozenset({"member", "admin"}),
    "agents:read": frozenset({"viewer", "member", "admin"}),
    "agents:run": frozenset({"member", "admin"}),
    "agents:manage": frozenset({"admin"}),
    "templates:read": frozenset({"viewer", "member", "admin"}),
    "templates:write": frozenset({"member", "admin"}),
    "organizations:read": frozenset({"viewer", "member", "admin"}),
    "organizations:manage": frozenset({"admin"}),
    "api_keys:manage": frozenset({"member", "admin"}),
    "credentials:read": frozenset({"admin"}),
    "credentials:manage": frozenset({"admin"}),
}

ALL_PERMISSIONS: Final[tuple[str, ...]] = tuple(sorted(PERMISSION_ROLES.keys()))


def is_valid_role(role: str) -> bool:
    return role in ROLE_RANK


def permissions_for_role(role: str) -> list[str]:
    """Return sorted permission codes granted to a role."""
    return sorted(
        permission
        for permission, roles in PERMISSION_ROLES.items()
        if role in roles
    )


def role_has_permission(role: str, permission: str) -> bool:
    allowed = PERMISSION_ROLES.get(permission)
    if allowed is None:
        return False
    return role in allowed


def role_at_least(role: str, minimum: RoleName) -> bool:
    return ROLE_RANK.get(role, 0) >= ROLE_RANK[minimum]
