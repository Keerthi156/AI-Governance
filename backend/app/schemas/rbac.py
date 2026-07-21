"""RBAC admin request/response schemas."""

from pydantic import BaseModel, Field

from app.core.rbac import ALL_PERMISSIONS, ROLES


class UpdateUserRequest(BaseModel):
    role: str | None = Field(
        default=None,
        description=f"One of: {', '.join(ROLES)}",
    )
    is_active: bool | None = None


class RoleCatalogResponse(BaseModel):
    roles: list[str] = Field(default_factory=lambda: list(ROLES))
    permissions: list[str] = Field(default_factory=lambda: list(ALL_PERMISSIONS))
    matrix: dict[str, list[str]]
