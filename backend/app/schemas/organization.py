"""Organization request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = Field(default=None, max_length=2000)


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrganizationMemberAdd(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    role: str = Field(default="member", pattern=r"^(viewer|member|admin)$")


class OrganizationMemberResponse(BaseModel):
    id: UUID
    user_id: UUID
    email: str
    full_name: str | None
    membership_role: str
    organization_id: UUID
    organization_slug: str
    created_at: datetime


class OrganizationInviteCreate(BaseModel):
    email: str | None = Field(
        default=None,
        max_length=320,
        description="Optional lock to a single email; omit for an open invite link",
    )
    role: str = Field(default="member", pattern=r"^(viewer|member|admin)$")
    expires_in_hours: int = Field(default=72, ge=1, le=720)


class OrganizationInviteResponse(BaseModel):
    id: UUID
    organization_id: UUID
    organization_slug: str
    email: str | None
    role: str
    token_hint: str
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    # Plaintext token only on create
    token: str | None = None
