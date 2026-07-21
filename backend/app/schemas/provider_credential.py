"""Provider credential (BYOK) request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProviderCredentialUpsert(BaseModel):
    api_key: str = Field(..., min_length=8, max_length=4096)
    notes: str | None = Field(default=None, max_length=2000)
    organization_slug: str = Field(default="default", max_length=100)


class ProviderCredentialResponse(BaseModel):
    id: UUID | None = None
    provider: str
    organization_id: UUID | None = None
    organization_slug: str
    has_credential: bool
    key_hint: str | None = None
    source: str = Field(description="org | env | none")
    env_configured: bool
    notes: str | None = None
    updated_at: datetime | None = None
