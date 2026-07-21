"""Data retention request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RetentionSettingsUpdate(BaseModel):
    prompt_history_retention_days: int | None = Field(
        default=None,
        ge=1,
        le=3650,
        description="Days to keep prompt history; null = keep forever",
    )
    audit_events_retention_days: int | None = Field(
        default=None,
        ge=1,
        le=3650,
        description="Days to keep audit events; null = keep forever",
    )
    retention_auto_purge_enabled: bool | None = Field(
        default=None,
        description="When true, the platform scheduler may purge expired rows",
    )
    organization_slug: str = Field(default="default", max_length=100)


class RetentionSettingsResponse(BaseModel):
    organization_id: UUID
    organization_slug: str
    prompt_history_retention_days: int | None
    audit_events_retention_days: int | None
    retention_auto_purge_enabled: bool
    retention_last_auto_purge_at: datetime | None
    prompt_history_total: int
    prompt_history_expired: int
    audit_events_total: int
    audit_events_expired: int


class RetentionPurgeRequest(BaseModel):
    organization_slug: str = Field(default="default", max_length=100)
    dry_run: bool = False


class RetentionPurgeResponse(BaseModel):
    organization_slug: str
    dry_run: bool
    prompt_history_deleted: int
    audit_events_deleted: int
    cutoff_prompt_history: datetime | None
    cutoff_audit_events: datetime | None


class RetentionSchedulerStatusResponse(BaseModel):
    enabled: bool
    interval_seconds: int
    initial_delay_seconds: int
    thread_alive: bool
    last_cycle_started_at: datetime | None
    last_cycle_finished_at: datetime | None
    last_error: str | None
    last_orgs_processed: int
    last_prompt_history_deleted: int
    last_audit_events_deleted: int
