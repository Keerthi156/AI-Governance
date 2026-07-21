"""
Audit log service — durable event writes + org-scoped queries.

Why this exists:
- Security/compliance needs an append-only trail independent of prompt history.
- Writes use a dedicated session so audit rows survive request rollbacks.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.audit import AuditEvent
from app.models.user import User
from app.schemas.audit import AuditEventListResponse, AuditEventResponse

logger = logging.getLogger("app.audit")

EXPORT_MAX_ROWS = 10_000

# Canonical action codes used across the platform.
KNOWN_ACTIONS: tuple[str, ...] = (
    "auth.register",
    "auth.login",
    "auth.login_failed",
    "auth.refresh",
    "auth.refresh_failed",
    "auth.logout",
    "users.update",
    "governance.policy.create",
    "governance.policy.update",
    "governance.policy.delete",
    "governance.policy_violation",
    "governance.spend_warn",
    "governance.pii_redact",
    "llm.completion",
    "llm.completion.stream",
    "arena.run",
    "router.route",
    "rag.ingest",
    "rag.ingest.upload",
    "rag.delete",
    "rag.query",
    "agents.definition.create",
    "agents.run",
    "agents.run.plan",
    "audit.export",
    "templates.create",
    "templates.delete",
    "organizations.create",
    "organizations.member_add",
    "organizations.member_remove",
    "organizations.invite_create",
    "organizations.invite_revoke",
    "organizations.invite_accept",
    "api_keys.create",
    "api_keys.revoke",
    "credentials.upsert",
    "credentials.delete",
    "webhooks.create",
    "webhooks.update",
    "webhooks.delete",
    "webhooks.test",
    "retention.update",
    "retention.purge",
    "retention.purge.scheduled",
    "compliance.report_export",
)


def record_event(
    *,
    action: str,
    status: str = "success",
    organization_id: UUID | None = None,
    actor: User | None = None,
    actor_email: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    request_id: str | None = None,
    summary: str | None = None,
    details: dict[str, Any] | None = None,
) -> UUID | None:
    """
    Persist an audit event on a dedicated DB session.

    Never raises to callers — audit must not break primary request flows.
    Returns the event id when persisted, otherwise None.
    """
    try:
        db = SessionLocal()
        try:
            event = AuditEvent(
                organization_id=organization_id or (actor.organization_id if actor else None),
                actor_user_id=actor.id if actor else None,
                actor_email=(
                    actor.email
                    if actor is not None
                    else (actor_email.lower().strip() if actor_email else None)
                ),
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                status=status,
                request_id=request_id,
                summary=summary,
                details=details,
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            event_id = event.id
            org_id = event.organization_id
            action_code = event.action
        finally:
            db.close()

        if org_id is not None:
            try:
                from app.services.webhook_service import dispatch_webhooks_for_event

                dispatch_webhooks_for_event(
                    event_id=event_id,
                    organization_id=org_id,
                    action=action_code,
                )
            except Exception:  # noqa: BLE001
                logger.exception("Webhook dispatch failed for action=%s", action)
        return event_id
    except Exception:  # noqa: BLE001
        logger.exception("Failed to persist audit event action=%s", action)
        return None


def event_to_response(row: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse(
        id=row.id,
        organization_id=row.organization_id,
        actor_user_id=row.actor_user_id,
        actor_email=row.actor_email,
        action=row.action,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        status=row.status,
        request_id=row.request_id,
        summary=row.summary,
        details=row.details,
        created_at=row.created_at,
    )


def list_audit_events(
    db: Session,
    *,
    organization_id: UUID,
    action: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> AuditEventListResponse:
    """List audit events for one organization (newest first)."""
    filters = _audit_filters(
        organization_id=organization_id,
        action=action,
        status=status,
    )

    total = db.scalar(select(func.count()).select_from(AuditEvent).where(*filters)) or 0
    rows = db.scalars(
        select(AuditEvent)
        .where(*filters)
        .order_by(AuditEvent.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return AuditEventListResponse(
        items=[event_to_response(row) for row in rows],
        total=int(total),
        page=page,
        page_size=page_size,
    )


def _audit_filters(
    *,
    organization_id: UUID,
    action: str | None = None,
    status: str | None = None,
) -> list[Any]:
    filters: list[Any] = [AuditEvent.organization_id == organization_id]
    if action:
        filters.append(AuditEvent.action == action)
    if status:
        filters.append(AuditEvent.status == status)
    return filters


def export_audit_events(
    db: Session,
    *,
    organization_id: UUID,
    action: str | None = None,
    status: str | None = None,
    limit: int = EXPORT_MAX_ROWS,
) -> list[AuditEventResponse]:
    """Return filtered audit rows for export (capped, newest first)."""
    filters = _audit_filters(
        organization_id=organization_id,
        action=action,
        status=status,
    )
    safe_limit = max(1, min(limit, EXPORT_MAX_ROWS))
    rows = db.scalars(
        select(AuditEvent)
        .where(*filters)
        .order_by(AuditEvent.created_at.desc())
        .limit(safe_limit)
    ).all()
    return [event_to_response(row) for row in rows]


def render_audit_export_csv(items: list[AuditEventResponse]) -> str:
    """Serialize audit events to CSV text."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "organization_id",
            "created_at",
            "action",
            "status",
            "actor_email",
            "actor_user_id",
            "resource_type",
            "resource_id",
            "request_id",
            "summary",
            "details",
        ]
    )
    for item in items:
        writer.writerow(
            [
                str(item.id),
                str(item.organization_id) if item.organization_id else "",
                item.created_at.isoformat() if item.created_at else "",
                item.action,
                item.status,
                item.actor_email or "",
                str(item.actor_user_id) if item.actor_user_id else "",
                item.resource_type or "",
                item.resource_id or "",
                item.request_id or "",
                item.summary or "",
                json.dumps(item.details, default=str) if item.details else "",
            ]
        )
    return buffer.getvalue()


def render_audit_export_json(items: list[AuditEventResponse]) -> str:
    """Serialize audit events to a JSON array string."""
    payload = [
        {
            "id": str(item.id),
            "organization_id": str(item.organization_id) if item.organization_id else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "action": item.action,
            "status": item.status,
            "actor_email": item.actor_email,
            "actor_user_id": str(item.actor_user_id) if item.actor_user_id else None,
            "resource_type": item.resource_type,
            "resource_id": item.resource_id,
            "request_id": item.request_id,
            "summary": item.summary,
            "details": item.details,
        }
        for item in items
    ]
    return json.dumps(payload, indent=2, default=str)
