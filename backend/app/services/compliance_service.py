"""
Compliance report service — aggregate org governance posture for export.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.api_key import ApiKey
from app.models.audit import AuditEvent
from app.models.user import User
from app.models.webhook import AuditWebhook
from app.schemas.compliance import (
    ComplianceCredentialStatus,
    ComplianceMemberSummary,
    CompliancePolicySummary,
    ComplianceReportResponse,
    ComplianceViolationItem,
)
from app.services.analytics_service import get_analytics_overview
from app.services.governance_service import list_policies, org_spend_snapshot
from app.services.organization_service import (
    list_organization_members,
    require_organization_access,
)
from app.services.provider_credential_service import list_provider_credentials
from app.services.retention_service import get_retention_settings


def build_compliance_report(
    db: Session,
    *,
    actor: User,
    organization_slug: str,
    days: int = 30,
) -> ComplianceReportResponse:
    days = max(1, min(days, 90))
    org = require_organization_access(db, organization_slug, actor=actor)

    retention = get_retention_settings(db, actor=actor, organization_slug=org.slug)
    members = list_organization_members(db, slug=org.slug, actor=actor)
    policies = list_policies(db, organization_slug=org.slug, active_only=False)
    credentials = list_provider_credentials(db, actor=actor, organization_slug=org.slug)
    spend_daily, spend_monthly = org_spend_snapshot(db, organization_id=org.id)
    analytics = get_analytics_overview(db, organization_slug=org.slug, days=days)

    webhook_count = (
        db.scalar(
            select(func.count())
            .select_from(AuditWebhook)
            .where(
                AuditWebhook.organization_id == org.id,
                AuditWebhook.is_active.is_(True),
            )
        )
        or 0
    )
    active_api_key_count = (
        db.scalar(
            select(func.count())
            .select_from(ApiKey)
            .where(
                ApiKey.organization_id == org.id,
                ApiKey.revoked_at.is_(None),
            )
        )
        or 0
    )

    violation_rows = db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.organization_id == org.id,
            AuditEvent.action.in_(
                (
                    "governance.policy_violation",
                    "governance.pii_redact",
                )
            ),
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(50)
    ).all()

    policy_summaries: list[CompliancePolicySummary] = []
    for policy in policies:
        rules = policy.rules
        policy_summaries.append(
            CompliancePolicySummary(
                id=policy.id,
                name=policy.name,
                is_active=policy.is_active,
                priority=policy.priority,
                blocked_providers=list(rules.blocked_providers or []),
                pii_block_categories=list(rules.pii_block_categories or []),
                pii_redact_categories=list(rules.pii_redact_categories or []),
                max_daily_cost_usd=rules.max_daily_cost_usd,
                max_monthly_cost_usd=rules.max_monthly_cost_usd,
                max_tokens_limit=rules.max_tokens_limit,
            )
        )

    active_policy_count = sum(1 for p in policies if p.is_active)
    controls = {
        "governance_policies_active": active_policy_count,
        "pii_blocking_enabled": any(
            p.is_active and (p.rules.pii_block_categories or []) for p in policies
        ),
        "spend_caps_enabled": any(
            p.is_active
            and (
                p.rules.max_daily_cost_usd is not None
                or p.rules.max_monthly_cost_usd is not None
            )
            for p in policies
        ),
        "retention_configured": (
            retention.prompt_history_retention_days is not None
            or retention.audit_events_retention_days is not None
        ),
        "retention_auto_purge_enabled": retention.retention_auto_purge_enabled,
        "spend_soft_warn_enabled": any(
            p.is_active
            and (
                p.rules.warn_daily_cost_usd is not None
                or p.rules.warn_monthly_cost_usd is not None
            )
            for p in policies
        ),
        "webhooks_configured": webhook_count > 0,
        "byok_org_keys": sum(1 for c in credentials if c.source == "org"),
    }

    return ComplianceReportResponse(
        generated_at=datetime.now(timezone.utc),
        organization_id=org.id,
        organization_slug=org.slug,
        organization_name=org.name,
        report_days=days,
        retention={
            "prompt_history_retention_days": retention.prompt_history_retention_days,
            "audit_events_retention_days": retention.audit_events_retention_days,
            "retention_auto_purge_enabled": retention.retention_auto_purge_enabled,
            "retention_last_auto_purge_at": (
                retention.retention_last_auto_purge_at.isoformat()
                if retention.retention_last_auto_purge_at
                else None
            ),
            "prompt_history_total": retention.prompt_history_total,
            "prompt_history_expired": retention.prompt_history_expired,
            "audit_events_total": retention.audit_events_total,
            "audit_events_expired": retention.audit_events_expired,
        },
        members=[
            ComplianceMemberSummary(
                email=m.user.email,
                membership_role=m.role,
                full_name=m.user.full_name,
            )
            for m in members
        ],
        policies=policy_summaries,
        credentials=[
            ComplianceCredentialStatus(
                provider=c.provider,
                source=c.source,
                has_credential=c.has_credential,
                env_configured=c.env_configured,
            )
            for c in credentials
        ],
        spend_daily_usd=spend_daily,
        spend_monthly_usd=spend_monthly,
        analytics_summary=analytics.summary.model_dump(mode="json"),
        webhook_count=webhook_count,
        active_api_key_count=active_api_key_count,
        recent_violations=[
            ComplianceViolationItem(
                id=row.id,
                action=row.action,
                status=row.status,
                summary=row.summary,
                created_at=row.created_at,
            )
            for row in violation_rows
        ],
        controls=controls,
    )
