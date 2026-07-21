"""Compliance report schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ComplianceMemberSummary(BaseModel):
    email: str
    membership_role: str
    full_name: str | None = None


class CompliancePolicySummary(BaseModel):
    id: UUID
    name: str
    is_active: bool
    priority: int
    blocked_providers: list[str] = Field(default_factory=list)
    pii_block_categories: list[str] = Field(default_factory=list)
    pii_redact_categories: list[str] = Field(default_factory=list)
    max_daily_cost_usd: Decimal | None = None
    max_monthly_cost_usd: Decimal | None = None
    max_tokens_limit: int | None = None


class ComplianceCredentialStatus(BaseModel):
    provider: str
    source: str
    has_credential: bool
    env_configured: bool


class ComplianceViolationItem(BaseModel):
    id: UUID
    action: str
    status: str
    summary: str | None
    created_at: datetime


class ComplianceReportResponse(BaseModel):
    generated_at: datetime
    organization_id: UUID
    organization_slug: str
    organization_name: str
    report_days: int
    retention: dict
    members: list[ComplianceMemberSummary]
    policies: list[CompliancePolicySummary]
    credentials: list[ComplianceCredentialStatus]
    spend_daily_usd: Decimal
    spend_monthly_usd: Decimal
    analytics_summary: dict
    webhook_count: int
    active_api_key_count: int
    recent_violations: list[ComplianceViolationItem]
    controls: dict
