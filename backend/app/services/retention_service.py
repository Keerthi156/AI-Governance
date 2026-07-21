"""
Data retention service — configure and purge expired org records.

Why this exists:
- Compliance often requires time-bounded retention of prompts and audit trails.
- Manual purge stays available; scheduled purge is opt-in per organization.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.organization import Organization
from app.models.prompt_history import PromptHistory
from app.models.user import User
from app.schemas.retention import (
    RetentionPurgeResponse,
    RetentionSettingsResponse,
    RetentionSettingsUpdate,
)
from app.services.organization_service import require_organization_access


def _cutoff(days: int | None) -> datetime | None:
    if days is None:
        return None
    return datetime.now(timezone.utc) - timedelta(days=days)


def _count_expired(
    db: Session,
    *,
    model,
    organization_id,
    cutoff: datetime | None,
) -> tuple[int, int]:
    total = (
        db.scalar(
            select(func.count())
            .select_from(model)
            .where(model.organization_id == organization_id)
        )
        or 0
    )
    if cutoff is None:
        return total, 0
    expired = (
        db.scalar(
            select(func.count())
            .select_from(model)
            .where(
                model.organization_id == organization_id,
                model.created_at < cutoff,
            )
        )
        or 0
    )
    return total, expired


def _settings_response(db: Session, org: Organization) -> RetentionSettingsResponse:
    ph_total, ph_expired = _count_expired(
        db,
        model=PromptHistory,
        organization_id=org.id,
        cutoff=_cutoff(org.prompt_history_retention_days),
    )
    audit_total, audit_expired = _count_expired(
        db,
        model=AuditEvent,
        organization_id=org.id,
        cutoff=_cutoff(org.audit_events_retention_days),
    )
    return RetentionSettingsResponse(
        organization_id=org.id,
        organization_slug=org.slug,
        prompt_history_retention_days=org.prompt_history_retention_days,
        audit_events_retention_days=org.audit_events_retention_days,
        retention_auto_purge_enabled=bool(org.retention_auto_purge_enabled),
        retention_last_auto_purge_at=org.retention_last_auto_purge_at,
        prompt_history_total=ph_total,
        prompt_history_expired=ph_expired,
        audit_events_total=audit_total,
        audit_events_expired=audit_expired,
    )


def get_retention_settings(
    db: Session,
    *,
    actor: User,
    organization_slug: str,
) -> RetentionSettingsResponse:
    org = require_organization_access(db, organization_slug, actor=actor)
    return _settings_response(db, org)


def update_retention_settings(
    db: Session,
    *,
    actor: User,
    body: RetentionSettingsUpdate,
) -> RetentionSettingsResponse:
    org = require_organization_access(db, body.organization_slug, actor=actor)
    org.prompt_history_retention_days = body.prompt_history_retention_days
    org.audit_events_retention_days = body.audit_events_retention_days
    if body.retention_auto_purge_enabled is not None:
        org.retention_auto_purge_enabled = body.retention_auto_purge_enabled
    db.add(org)
    db.commit()
    db.refresh(org)
    return _settings_response(db, org)


def purge_expired_for_organization(
    db: Session,
    org: Organization,
    *,
    dry_run: bool = False,
) -> RetentionPurgeResponse:
    """Purge (or count) expired rows for a loaded organization — no actor check."""
    ph_cutoff = _cutoff(org.prompt_history_retention_days)
    audit_cutoff = _cutoff(org.audit_events_retention_days)

    ph_deleted = 0
    audit_deleted = 0

    if ph_cutoff is not None:
        if dry_run:
            ph_deleted = (
                db.scalar(
                    select(func.count())
                    .select_from(PromptHistory)
                    .where(
                        PromptHistory.organization_id == org.id,
                        PromptHistory.created_at < ph_cutoff,
                    )
                )
                or 0
            )
        else:
            result = db.execute(
                delete(PromptHistory).where(
                    PromptHistory.organization_id == org.id,
                    PromptHistory.created_at < ph_cutoff,
                )
            )
            ph_deleted = result.rowcount or 0

    if audit_cutoff is not None:
        if dry_run:
            audit_deleted = (
                db.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(
                        AuditEvent.organization_id == org.id,
                        AuditEvent.created_at < audit_cutoff,
                    )
                )
                or 0
            )
        else:
            result = db.execute(
                delete(AuditEvent).where(
                    AuditEvent.organization_id == org.id,
                    AuditEvent.created_at < audit_cutoff,
                )
            )
            audit_deleted = result.rowcount or 0

    if not dry_run:
        db.commit()

    return RetentionPurgeResponse(
        organization_slug=org.slug,
        dry_run=dry_run,
        prompt_history_deleted=ph_deleted,
        audit_events_deleted=audit_deleted,
        cutoff_prompt_history=ph_cutoff,
        cutoff_audit_events=audit_cutoff,
    )


def purge_expired_records(
    db: Session,
    *,
    actor: User,
    organization_slug: str,
    dry_run: bool = False,
) -> RetentionPurgeResponse:
    org = require_organization_access(db, organization_slug, actor=actor)
    return purge_expired_for_organization(db, org, dry_run=dry_run)


def list_auto_purge_organizations(db: Session) -> list[Organization]:
    """Orgs that opted into scheduled purge and have at least one retention window."""
    return list(
        db.scalars(
            select(Organization).where(
                Organization.retention_auto_purge_enabled.is_(True),
            )
        ).all()
    )
