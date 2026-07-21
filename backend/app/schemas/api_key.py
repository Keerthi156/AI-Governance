"""API key request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(default="member", pattern=r"^(viewer|member|admin)$")
    organization_slug: str = Field(default="default", max_length=100)
    expires_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ApiKeyResponse(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    role: str
    organization_id: UUID
    organization_slug: str
    user_id: UUID
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    notes: str | None
    created_at: datetime
    is_active: bool


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Returned once at creation — includes the plaintext secret."""

    api_key: str = Field(..., description="Full secret; store it now, it is not shown again")
