"""Prompt template request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PromptTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1, max_length=20_000)
    description: str | None = Field(default=None, max_length=2000)
    default_provider: str = Field(default="groq", max_length=50)
    default_model: str | None = Field(default=None, max_length=100)
    organization_slug: str = Field(default="default", max_length=100)


class PromptTemplateResponse(BaseModel):
    id: UUID
    organization_id: UUID
    organization_slug: str
    name: str
    description: str | None
    body: str
    default_provider: str
    default_model: str | None
    is_system: bool
    created_at: datetime

    model_config = {"from_attributes": True}
