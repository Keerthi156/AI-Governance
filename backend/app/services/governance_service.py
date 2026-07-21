"""
Governance policy service — CRUD + enforcement evaluation.

Why this exists:
- Keeps policy logic out of route handlers and provider clients.
- All active org policies are AND-ed: any matching deny blocks the request.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import NotFoundError, PolicyViolationError, ValidationAppError
from app.models.governance import GovernancePolicy
from app.models.organization import Organization
from app.models.prompt_history import PromptHistory
from app.schemas.governance import (
    PiiFindingItem,
    PolicyCreateRequest,
    PolicyEvaluateResponse,
    PolicyResponse,
    PolicyRules,
    PolicyUpdateRequest,
    PolicyViolationItem,
)
from app.services.audit_service import record_event
from app.services.organization_service import get_or_create_organization
from app.services.pii_scanner import (
    normalize_pii_categories,
    redact_pii,
    scan_pii,
)
from app.services.provider_registry import resolve_model


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    violations: list[PolicyViolationItem]
    warnings: list[PolicyViolationItem] = field(default_factory=list)
    spend_daily_usd: Decimal = Decimal("0")
    spend_monthly_usd: Decimal = Decimal("0")
    sanitized_prompt: str = ""
    pii_findings: tuple[PiiFindingItem, ...] = ()


def _rules_from_row(row: GovernancePolicy) -> PolicyRules:
    raw = row.rules or {}
    return PolicyRules.model_validate(raw)


def _utc_day_start(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def _utc_month_start(now: datetime | None = None) -> datetime:
    day_start = _utc_day_start(now)
    return day_start.replace(day=1)


def sum_org_spend_usd(
    db: Session,
    *,
    organization_id: UUID,
    since: datetime,
) -> Decimal:
    """Sum estimated_cost_usd for successful completions since `since` (inclusive)."""
    total = db.scalar(
        select(func.coalesce(func.sum(PromptHistory.estimated_cost_usd), 0)).where(
            PromptHistory.organization_id == organization_id,
            PromptHistory.status == "success",
            PromptHistory.estimated_cost_usd.is_not(None),
            PromptHistory.created_at >= since,
        )
    )
    return Decimal(str(total or 0))


def org_spend_snapshot(
    db: Session,
    *,
    organization_id: UUID,
) -> tuple[Decimal, Decimal]:
    """Return (daily_usd, monthly_usd) spend for the organization (UTC windows)."""
    daily = sum_org_spend_usd(
        db, organization_id=organization_id, since=_utc_day_start()
    )
    monthly = sum_org_spend_usd(
        db, organization_id=organization_id, since=_utc_month_start()
    )
    return daily, monthly


def policy_to_response(row: GovernancePolicy) -> PolicyResponse:
    return PolicyResponse(
        id=row.id,
        organization_id=row.organization_id,
        organization_slug=row.organization.slug,
        name=row.name,
        description=row.description,
        is_active=row.is_active,
        priority=row.priority,
        rules=_rules_from_row(row),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_policies(
    db: Session,
    *,
    organization_slug: str = "default",
    active_only: bool = False,
) -> list[PolicyResponse]:
    org = db.scalar(
        select(Organization).where(Organization.slug == organization_slug.strip().lower())
    )
    if org is None:
        return []

    stmt = (
        select(GovernancePolicy)
        .options(joinedload(GovernancePolicy.organization))
        .where(GovernancePolicy.organization_id == org.id)
        .order_by(GovernancePolicy.priority.desc(), GovernancePolicy.created_at.asc())
    )
    if active_only:
        stmt = stmt.where(GovernancePolicy.is_active.is_(True))
    rows = db.scalars(stmt).all()
    return [policy_to_response(row) for row in rows]


def get_policy(db: Session, policy_id: UUID) -> GovernancePolicy:
    row = db.scalar(
        select(GovernancePolicy)
        .options(joinedload(GovernancePolicy.organization))
        .where(GovernancePolicy.id == policy_id)
    )
    if row is None:
        raise NotFoundError("Policy not found")
    return row


def create_policy(db: Session, body: PolicyCreateRequest) -> PolicyResponse:
    org = get_or_create_organization(db, slug=body.organization_slug.strip().lower())
    row = GovernancePolicy(
        organization_id=org.id,
        name=body.name.strip(),
        description=body.description.strip() if body.description else None,
        is_active=body.is_active,
        priority=body.priority,
        rules=body.rules.model_dump(mode="json"),
    )
    db.add(row)
    db.commit()
    return policy_to_response(get_policy(db, row.id))


def update_policy(
    db: Session,
    policy_id: UUID,
    body: PolicyUpdateRequest,
) -> PolicyResponse:
    row = get_policy(db, policy_id)
    if body.name is not None:
        row.name = body.name.strip()
    if body.description is not None:
        row.description = body.description.strip() or None
    if body.is_active is not None:
        row.is_active = body.is_active
    if body.priority is not None:
        row.priority = body.priority
    if body.rules is not None:
        row.rules = body.rules.model_dump(mode="json")
    db.add(row)
    db.commit()
    return policy_to_response(get_policy(db, row.id))


def delete_policy(db: Session, policy_id: UUID) -> None:
    row = get_policy(db, policy_id)
    db.delete(row)
    db.commit()


def evaluate_request(
    db: Session,
    *,
    organization_id: UUID,
    provider: str,
    model: str,
    prompt: str,
    max_tokens: int,
) -> PolicyDecision:
    """Evaluate all active policies for an organization against a request."""
    rows = db.scalars(
        select(GovernancePolicy)
        .where(
            GovernancePolicy.organization_id == organization_id,
            GovernancePolicy.is_active.is_(True),
        )
        .order_by(GovernancePolicy.priority.desc())
    ).all()

    provider_key = provider.strip().lower()
    model_key = model.strip()
    prompt_lower = prompt.lower()
    violations: list[PolicyViolationItem] = []

    spend_daily, spend_monthly = org_spend_snapshot(
        db, organization_id=organization_id
    )

    warnings: list[PolicyViolationItem] = []

    for row in rows:
        rules = _rules_from_row(row)

        if rules.allowed_providers is not None:
            allowed = {p.strip().lower() for p in rules.allowed_providers}
            if provider_key not in allowed:
                violations.append(
                    PolicyViolationItem(
                        policy_id=row.id,
                        policy_name=row.name,
                        rule="allowed_providers",
                        message=f"Provider '{provider_key}' is not in the allow-list",
                    )
                )

        blocked_providers = {p.strip().lower() for p in rules.blocked_providers}
        if provider_key in blocked_providers:
            violations.append(
                PolicyViolationItem(
                    policy_id=row.id,
                    policy_name=row.name,
                    rule="blocked_providers",
                    message=f"Provider '{provider_key}' is blocked by policy",
                )
            )

        if rules.allowed_models is not None:
            allowed_models = {m.strip() for m in rules.allowed_models}
            if model_key not in allowed_models:
                violations.append(
                    PolicyViolationItem(
                        policy_id=row.id,
                        policy_name=row.name,
                        rule="allowed_models",
                        message=f"Model '{model_key}' is not in the allow-list",
                    )
                )

        blocked_models = {m.strip() for m in rules.blocked_models}
        if model_key in blocked_models:
            violations.append(
                PolicyViolationItem(
                    policy_id=row.id,
                    policy_name=row.name,
                    rule="blocked_models",
                    message=f"Model '{model_key}' is blocked by policy",
                )
            )

        if rules.max_tokens_limit is not None and max_tokens > rules.max_tokens_limit:
            violations.append(
                PolicyViolationItem(
                    policy_id=row.id,
                    policy_name=row.name,
                    rule="max_tokens_limit",
                    message=(
                        f"max_tokens {max_tokens} exceeds policy limit "
                        f"{rules.max_tokens_limit}"
                    ),
                )
            )

        for pattern in rules.blocked_prompt_patterns:
            needle = pattern.strip().lower()
            if needle and needle in prompt_lower:
                violations.append(
                    PolicyViolationItem(
                        policy_id=row.id,
                        policy_name=row.name,
                        rule="blocked_prompt_patterns",
                        message=f"Prompt matches blocked pattern '{pattern}'",
                    )
                )

        if rules.max_daily_cost_usd is not None and spend_daily >= rules.max_daily_cost_usd:
            violations.append(
                PolicyViolationItem(
                    policy_id=row.id,
                    policy_name=row.name,
                    rule="max_daily_cost_usd",
                    message=(
                        f"Daily spend ${spend_daily:.6f} has reached the policy cap "
                        f"${rules.max_daily_cost_usd}"
                    ),
                )
            )

        if (
            rules.max_monthly_cost_usd is not None
            and spend_monthly >= rules.max_monthly_cost_usd
        ):
            violations.append(
                PolicyViolationItem(
                    policy_id=row.id,
                    policy_name=row.name,
                    rule="max_monthly_cost_usd",
                    message=(
                        f"Monthly spend ${spend_monthly:.6f} has reached the policy cap "
                        f"${rules.max_monthly_cost_usd}"
                    ),
                )
            )

        if (
            rules.warn_daily_cost_usd is not None
            and spend_daily >= rules.warn_daily_cost_usd
            and (
                rules.max_daily_cost_usd is None
                or spend_daily < rules.max_daily_cost_usd
            )
        ):
            warnings.append(
                PolicyViolationItem(
                    policy_id=row.id,
                    policy_name=row.name,
                    rule="warn_daily_cost_usd",
                    message=(
                        f"Daily spend ${spend_daily:.6f} has reached the soft-warn "
                        f"threshold ${rules.warn_daily_cost_usd}"
                    ),
                )
            )

        if (
            rules.warn_monthly_cost_usd is not None
            and spend_monthly >= rules.warn_monthly_cost_usd
            and (
                rules.max_monthly_cost_usd is None
                or spend_monthly < rules.max_monthly_cost_usd
            )
        ):
            warnings.append(
                PolicyViolationItem(
                    policy_id=row.id,
                    policy_name=row.name,
                    rule="warn_monthly_cost_usd",
                    message=(
                        f"Monthly spend ${spend_monthly:.6f} has reached the soft-warn "
                        f"threshold ${rules.warn_monthly_cost_usd}"
                    ),
                )
            )

        block_cats = normalize_pii_categories(rules.pii_block_categories)
        if block_cats:
            for finding in scan_pii(prompt, categories=block_cats):
                violations.append(
                    PolicyViolationItem(
                        policy_id=row.id,
                        policy_name=row.name,
                        rule="pii_block_categories",
                        message=(
                            f"Prompt contains blocked PII/secret ({finding.category}: "
                            f"{finding.label})"
                        ),
                    )
                )

    redact_cats: list[str] = []
    for row in rows:
        rules = _rules_from_row(row)
        for cat in normalize_pii_categories(rules.pii_redact_categories):
            if cat not in redact_cats:
                redact_cats.append(cat)

    # Findings for dry-run / audit (union of block+redact categories across policies).
    scan_cats = list(
        dict.fromkeys(
            [
                *redact_cats,
                *[
                    cat
                    for row in rows
                    for cat in normalize_pii_categories(
                        _rules_from_row(row).pii_block_categories
                    )
                ],
            ]
        )
    )
    all_findings = scan_pii(prompt, categories=scan_cats) if scan_cats else []
    finding_items = tuple(
        PiiFindingItem(category=f.category, label=f.label) for f in all_findings
    )

    sanitized = prompt
    if redact_cats and len(violations) == 0:
        sanitized, _ = redact_pii(prompt, redact_cats)

    return PolicyDecision(
        allowed=len(violations) == 0,
        violations=violations,
        warnings=warnings,
        spend_daily_usd=spend_daily,
        spend_monthly_usd=spend_monthly,
        sanitized_prompt=sanitized,
        pii_findings=finding_items,
    )


def assert_request_allowed(
    db: Session,
    *,
    organization_id: UUID,
    provider: str,
    model: str,
    prompt: str,
    max_tokens: int,
) -> str:
    """
    Enforce active policies. Returns the prompt to send (possibly redacted).
    Raises PolicyViolationError when denied.
    """
    decision = evaluate_request(
        db,
        organization_id=organization_id,
        provider=provider,
        model=model,
        prompt=prompt,
        max_tokens=max_tokens,
    )
    if decision.allowed:
        if decision.warnings:
            record_event(
                action="governance.spend_warn",
                status="warning",
                organization_id=organization_id,
                resource_type="llm_request",
                summary="; ".join(w.message for w in decision.warnings),
                details={
                    "provider": provider,
                    "model": model,
                    "spend_daily_usd": str(decision.spend_daily_usd),
                    "spend_monthly_usd": str(decision.spend_monthly_usd),
                    "warnings": [w.model_dump(mode="json") for w in decision.warnings],
                },
            )
        if decision.sanitized_prompt != prompt and decision.pii_findings:
            record_event(
                action="governance.pii_redact",
                status="success",
                organization_id=organization_id,
                resource_type="llm_request",
                summary=(
                    "Redacted PII/secrets in prompt: "
                    + ", ".join(sorted({f.category for f in decision.pii_findings}))
                ),
                details={
                    "provider": provider,
                    "model": model,
                    "findings": [f.model_dump() for f in decision.pii_findings],
                },
            )
        return decision.sanitized_prompt

    messages = [v.message for v in decision.violations]
    record_event(
        action="governance.policy_violation",
        status="denied",
        organization_id=organization_id,
        resource_type="llm_request",
        summary="; ".join(messages),
        details={
            "provider": provider,
            "model": model,
            "max_tokens": max_tokens,
            "spend_daily_usd": str(decision.spend_daily_usd),
            "spend_monthly_usd": str(decision.spend_monthly_usd),
            "pii_findings": [f.model_dump() for f in decision.pii_findings],
            "violations": [v.model_dump(mode="json") for v in decision.violations],
        },
    )
    raise PolicyViolationError(
        "; ".join(messages),
        details={
            "violations": [v.model_dump(mode="json") for v in decision.violations],
            "spend_daily_usd": str(decision.spend_daily_usd),
            "spend_monthly_usd": str(decision.spend_monthly_usd),
            "pii_findings": [f.model_dump() for f in decision.pii_findings],
        },
    )


def dry_run_evaluate(
    db: Session,
    *,
    organization_slug: str,
    provider: str,
    model: str | None,
    prompt: str,
    max_tokens: int,
) -> PolicyEvaluateResponse:
    from app.services.provider_registry import SUPPORTED_PROVIDERS

    org = get_or_create_organization(db, slug=organization_slug.strip().lower())
    provider_key = provider.strip().lower()
    if not prompt.strip():
        raise ValidationAppError("Prompt must not be empty.")
    if provider_key not in SUPPORTED_PROVIDERS:
        raise ValidationAppError(
            f"Unsupported provider '{provider}'. Supported: {sorted(SUPPORTED_PROVIDERS)}"
        )
    resolved = resolve_model(provider_key, model)

    decision = evaluate_request(
        db,
        organization_id=org.id,
        provider=provider_key,
        model=resolved,
        prompt=prompt,
        max_tokens=max_tokens,
    )
    return PolicyEvaluateResponse(
        allowed=decision.allowed,
        organization_slug=org.slug,
        violations=decision.violations,
        warnings=decision.warnings,
        spend_daily_usd=decision.spend_daily_usd,
        spend_monthly_usd=decision.spend_monthly_usd,
        pii_findings=list(decision.pii_findings),
        sanitized_prompt=decision.sanitized_prompt if decision.allowed else None,
    )
