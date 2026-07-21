"""Governance policy request/response schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class PolicyRules(BaseModel):
    """
    Guardrail rules evaluated against an LLM request.

    Empty / null allow-lists mean "no restriction" for that field.
    Cost caps use successful prompt_history estimated_cost_usd (UTC windows).
    """

    allowed_providers: list[str] | None = Field(
        default=None,
        description="If set, only these providers may be used",
    )
    blocked_providers: list[str] = Field(default_factory=list)
    allowed_models: list[str] | None = Field(
        default=None,
        description="If set, only these models may be used",
    )
    blocked_models: list[str] = Field(default_factory=list)
    max_tokens_limit: int | None = Field(
        default=None,
        ge=1,
        le=8192,
        description="Hard cap on max_tokens for completions",
    )
    blocked_prompt_patterns: list[str] = Field(
        default_factory=list,
        description="Case-insensitive substrings that deny the prompt",
    )
    max_daily_cost_usd: Decimal | None = Field(
        default=None,
        ge=0,
        description="Deny when org UTC-day spend reaches this USD amount",
    )
    max_monthly_cost_usd: Decimal | None = Field(
        default=None,
        ge=0,
        description="Deny when org UTC-month spend reaches this USD amount",
    )
    warn_daily_cost_usd: Decimal | None = Field(
        default=None,
        ge=0,
        description="Soft-warn (allow) when UTC-day spend reaches this amount",
    )
    warn_monthly_cost_usd: Decimal | None = Field(
        default=None,
        ge=0,
        description="Soft-warn (allow) when UTC-month spend reaches this amount",
    )
    pii_block_categories: list[str] = Field(
        default_factory=list,
        description=(
            "PII/secret categories that deny the request when detected "
            "(ssn, email, phone, credit_card, aws_key, api_key, private_key)"
        ),
    )
    pii_redact_categories: list[str] = Field(
        default_factory=list,
        description="PII/secret categories to replace with [REDACTED:…] before the LLM call",
    )


class PolicyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True
    priority: int = Field(default=100, ge=0, le=10000)
    rules: PolicyRules = Field(default_factory=PolicyRules)
    organization_slug: str = Field(default="default", max_length=100)


class PolicyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=10000)
    rules: PolicyRules | None = None


class PolicyResponse(BaseModel):
    id: UUID
    organization_id: UUID
    organization_slug: str
    name: str
    description: str | None
    is_active: bool
    priority: int
    rules: PolicyRules
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PolicyEvaluateRequest(BaseModel):
    provider: str
    model: str | None = None
    prompt: str = Field(..., min_length=1)
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    organization_slug: str = Field(default="default", max_length=100)


class PolicyViolationItem(BaseModel):
    policy_id: UUID
    policy_name: str
    rule: str
    message: str


class PiiFindingItem(BaseModel):
    category: str
    label: str


class PolicyEvaluateResponse(BaseModel):
    allowed: bool
    organization_slug: str
    violations: list[PolicyViolationItem]
    warnings: list[PolicyViolationItem] = Field(default_factory=list)
    spend_daily_usd: Decimal = Field(
        default=Decimal("0"),
        description="Org successful spend since UTC midnight",
    )
    spend_monthly_usd: Decimal = Field(
        default=Decimal("0"),
        description="Org successful spend since UTC month start",
    )
    pii_findings: list[PiiFindingItem] = Field(default_factory=list)
    sanitized_prompt: str | None = Field(
        default=None,
        description="Prompt after redaction (when allowed and redact rules apply)",
    )
