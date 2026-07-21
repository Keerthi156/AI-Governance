"""Audit log request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AuditEventResponse(BaseModel):
    id: UUID
    organization_id: UUID | None
    actor_user_id: UUID | None
    actor_email: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    status: str
    request_id: str | None
    summary: str | None
    details: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditEventListResponse(BaseModel):
    items: list[AuditEventResponse]
    total: int
    page: int
    page_size: int


class AuditActionCatalogResponse(BaseModel):
    actions: list[str] = Field(
        ...,
        description="Known action codes written by the platform",
    )
