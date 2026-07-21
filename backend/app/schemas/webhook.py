"""Audit webhook request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WebhookCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=8, max_length=2000)
    secret: str = Field(..., min_length=8, max_length=256)
    action_filters: list[str] | None = Field(
        default=None,
        description="If set, only these audit action codes are delivered",
    )
    is_active: bool = True
    organization_slug: str = Field(default="default", max_length=100)


class WebhookUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    url: str | None = Field(default=None, min_length=8, max_length=2000)
    secret: str | None = Field(default=None, min_length=8, max_length=256)
    action_filters: list[str] | None = None
    is_active: bool | None = None


class WebhookResponse(BaseModel):
    id: UUID
    organization_id: UUID
    organization_slug: str
    name: str
    url: str
    secret_hint: str
    action_filters: list[str] | None
    is_active: bool
    last_delivery_at: datetime | None
    last_status_code: int | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class WebhookDeliveryResponse(BaseModel):
    id: UUID
    webhook_id: UUID
    webhook_name: str | None = None
    audit_event_id: UUID | None
    attempt_number: int
    status: str
    http_status_code: int | None
    error_message: str | None
    response_snippet: str | None
    next_retry_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WebhookDeliveryListResponse(BaseModel):
    items: list[WebhookDeliveryResponse]
    total: int
