"""Auth request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    organization_slug: str = Field(default="default", max_length=100)
    invite_token: str | None = Field(
        default=None,
        max_length=200,
        description="Optional org invite token (agi_…) to join an existing org",
    )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=20, max_length=200)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, max_length=200)


class InviteAcceptRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=200)
    password: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
        description="Required when creating a new account via invite",
    )
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(
        default=None,
        description="Required for open invites (no email locked on the invite)",
    )


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str | None
    role: str
    is_active: bool
    organization_id: UUID
    organization_slug: str
    permissions: list[str] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Seconds until access token expiry")
    refresh_token: str | None = Field(
        default=None,
        description="Opaque refresh token (store client-side; shown once per issue)",
    )
    refresh_expires_in: int | None = Field(
        default=None,
        description="Seconds until refresh token expiry",
    )
    user: UserResponse
