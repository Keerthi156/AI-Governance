"""
Audit webhook service — CRUD, signed HTTPS delivery, retries + delivery log.

Why this exists:
- Enterprises need audit events in SIEM / Slack / custom collectors.
- Delivery is best-effort and must never break primary request flows.
- Retries + durable attempt rows make failures diagnosable and recoverable.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.credential_crypto import decrypt_secret, encrypt_secret, key_hint
from app.core.database import SessionLocal
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.audit import AuditEvent
from app.models.user import User
from app.models.webhook import AuditWebhook, AuditWebhookDelivery
from app.schemas.webhook import (
    WebhookCreateRequest,
    WebhookDeliveryListResponse,
    WebhookDeliveryResponse,
    WebhookResponse,
    WebhookUpdateRequest,
)
from app.services.organization_service import require_organization_access

logger = logging.getLogger("app.webhooks")

DELIVERY_TIMEOUT_SECONDS = 5.0
STATUS_PENDING = "pending"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_EXHAUSTED = "exhausted"


def _validate_url(url: str) -> str:
    cleaned = url.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"https", "http"}:
        raise ValidationAppError("Webhook URL must start with http:// or https://")
    if not parsed.netloc:
        raise ValidationAppError("Webhook URL is missing a host")
    return cleaned


def _backoff_seconds(attempt_number: int) -> int:
    """Exponential backoff: base * 2^(attempt-1)."""
    settings = get_settings()
    base = max(1, settings.webhook_retry_base_seconds)
    return base * (2 ** max(0, attempt_number - 1))


def webhook_to_response(row: AuditWebhook) -> WebhookResponse:
    return WebhookResponse(
        id=row.id,
        organization_id=row.organization_id,
        organization_slug=row.organization.slug,
        name=row.name,
        url=row.url,
        secret_hint=row.secret_hint,
        action_filters=list(row.action_filters) if row.action_filters else None,
        is_active=row.is_active,
        last_delivery_at=row.last_delivery_at,
        last_status_code=row.last_status_code,
        last_error=row.last_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def delivery_to_response(
    row: AuditWebhookDelivery,
    *,
    webhook_name: str | None = None,
) -> WebhookDeliveryResponse:
    return WebhookDeliveryResponse(
        id=row.id,
        webhook_id=row.webhook_id,
        webhook_name=webhook_name,
        audit_event_id=row.audit_event_id,
        attempt_number=row.attempt_number,
        status=row.status,
        http_status_code=row.http_status_code,
        error_message=row.error_message,
        response_snippet=row.response_snippet,
        next_retry_at=row.next_retry_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_webhooks(
    db: Session,
    *,
    actor: User,
    organization_slug: str,
) -> list[WebhookResponse]:
    org = require_organization_access(db, organization_slug, actor=actor)
    rows = db.scalars(
        select(AuditWebhook)
        .options(joinedload(AuditWebhook.organization))
        .where(AuditWebhook.organization_id == org.id)
        .order_by(AuditWebhook.created_at.desc())
    ).all()
    return [webhook_to_response(row) for row in rows]


def create_webhook(
    db: Session,
    *,
    actor: User,
    body: WebhookCreateRequest,
) -> WebhookResponse:
    org = require_organization_access(db, body.organization_slug, actor=actor)
    url = _validate_url(body.url)
    secret = body.secret.strip()
    filters = [a.strip() for a in (body.action_filters or []) if a.strip()] or None

    row = AuditWebhook(
        organization_id=org.id,
        name=body.name.strip(),
        url=url,
        secret_ciphertext=encrypt_secret(secret),
        secret_hint=key_hint(secret),
        action_filters=filters,
        is_active=body.is_active,
    )
    db.add(row)
    db.commit()
    row = db.scalar(
        select(AuditWebhook)
        .options(joinedload(AuditWebhook.organization))
        .where(AuditWebhook.id == row.id)
    )
    assert row is not None
    return webhook_to_response(row)


def update_webhook(
    db: Session,
    *,
    actor: User,
    webhook_id: UUID,
    body: WebhookUpdateRequest,
) -> WebhookResponse:
    row = db.scalar(
        select(AuditWebhook)
        .options(joinedload(AuditWebhook.organization))
        .where(AuditWebhook.id == webhook_id)
    )
    if row is None:
        raise NotFoundError("Webhook not found")
    require_organization_access(db, row.organization.slug, actor=actor)

    if body.name is not None:
        row.name = body.name.strip()
    if body.url is not None:
        row.url = _validate_url(body.url)
    if body.secret is not None:
        secret = body.secret.strip()
        row.secret_ciphertext = encrypt_secret(secret)
        row.secret_hint = key_hint(secret)
    if body.action_filters is not None:
        filters = [a.strip() for a in body.action_filters if a.strip()]
        row.action_filters = filters or None
    if body.is_active is not None:
        row.is_active = body.is_active

    db.add(row)
    db.commit()
    db.refresh(row)
    row = db.scalar(
        select(AuditWebhook)
        .options(joinedload(AuditWebhook.organization))
        .where(AuditWebhook.id == webhook_id)
    )
    assert row is not None
    return webhook_to_response(row)


def delete_webhook(db: Session, *, actor: User, webhook_id: UUID) -> None:
    row = db.scalar(
        select(AuditWebhook)
        .options(joinedload(AuditWebhook.organization))
        .where(AuditWebhook.id == webhook_id)
    )
    if row is None:
        raise NotFoundError("Webhook not found")
    require_organization_access(db, row.organization.slug, actor=actor)
    db.delete(row)
    db.commit()


def list_deliveries(
    db: Session,
    *,
    actor: User,
    organization_slug: str,
    webhook_id: UUID | None = None,
    limit: int = 50,
) -> WebhookDeliveryListResponse:
    org = require_organization_access(db, organization_slug, actor=actor)
    limit = max(1, min(limit, 200))

    base = (
        select(AuditWebhookDelivery)
        .join(AuditWebhook, AuditWebhookDelivery.webhook_id == AuditWebhook.id)
        .options(joinedload(AuditWebhookDelivery.webhook))
        .where(AuditWebhook.organization_id == org.id)
    )
    if webhook_id is not None:
        base = base.where(AuditWebhookDelivery.webhook_id == webhook_id)

    count_q = (
        select(func.count())
        .select_from(AuditWebhookDelivery)
        .join(AuditWebhook, AuditWebhookDelivery.webhook_id == AuditWebhook.id)
        .where(AuditWebhook.organization_id == org.id)
    )
    if webhook_id is not None:
        count_q = count_q.where(AuditWebhookDelivery.webhook_id == webhook_id)
    total = db.scalar(count_q) or 0

    rows = db.scalars(
        base.order_by(AuditWebhookDelivery.created_at.desc()).limit(limit)
    ).all()
    return WebhookDeliveryListResponse(
        items=[
            delivery_to_response(
                row,
                webhook_name=row.webhook.name if row.webhook else None,
            )
            for row in rows
        ],
        total=total,
    )


def _event_payload(event: AuditEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "organization_id": str(event.organization_id) if event.organization_id else None,
        "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
        "actor_email": event.actor_email,
        "action": event.action,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "status": event.status,
        "request_id": event.request_id,
        "summary": event.summary,
        "details": event.details,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def _sign_body(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _matches_filters(row: AuditWebhook, action: str) -> bool:
    filters = row.action_filters or []
    if not filters:
        return True
    return action in filters


def _http_post(webhook: AuditWebhook, event: AuditEvent) -> tuple[int | None, str | None, str | None]:
    """
    POST the signed payload.

    Returns (http_status, error_message, response_snippet).
    http_status is None on transport failure.
    """
    secret = decrypt_secret(webhook.secret_ciphertext)
    payload = {
        "type": "audit.event",
        "webhook_id": str(webhook.id),
        "delivery_attempt": True,
        "event": _event_payload(event),
    }
    body = json.dumps(payload, default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "AI-GOVERNANCE-Webhooks/1.0",
        "X-AI-Governance-Signature": _sign_body(secret, body),
        "X-AI-Governance-Event": event.action,
    }
    try:
        with httpx.Client(timeout=DELIVERY_TIMEOUT_SECONDS) as client:
            response = client.post(webhook.url, content=body, headers=headers)
        snippet = (response.text or "")[:300] or None
        if 200 <= response.status_code < 300:
            return response.status_code, None, snippet
        return (
            response.status_code,
            f"HTTP {response.status_code}: {(response.text or '')[:300]}",
            snippet,
        )
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)[:500], None


def _update_webhook_last(
    db: Session,
    webhook: AuditWebhook,
    *,
    status_code: int | None,
    error: str | None,
) -> None:
    webhook.last_delivery_at = datetime.now(timezone.utc)
    webhook.last_status_code = status_code
    webhook.last_error = error
    db.add(webhook)


def _schedule_retry_or_exhaust(
    db: Session,
    *,
    webhook: AuditWebhook,
    event_id: UUID,
    failed_attempt: int,
    http_status: int | None,
    error: str | None,
    snippet: str | None,
) -> None:
    settings = get_settings()
    max_attempts = max(1, settings.webhook_max_attempts)

    if failed_attempt >= max_attempts:
        delivery = AuditWebhookDelivery(
            webhook_id=webhook.id,
            audit_event_id=event_id,
            attempt_number=failed_attempt,
            status=STATUS_EXHAUSTED,
            http_status_code=http_status,
            error_message=error,
            response_snippet=snippet,
            next_retry_at=None,
        )
        db.add(delivery)
        _update_webhook_last(db, webhook, status_code=http_status, error=error)
        db.commit()
        return

    next_attempt = failed_attempt + 1
    delay = _backoff_seconds(failed_attempt)
    pending = AuditWebhookDelivery(
        webhook_id=webhook.id,
        audit_event_id=event_id,
        attempt_number=next_attempt,
        status=STATUS_PENDING,
        http_status_code=http_status,
        error_message=error,
        response_snippet=snippet,
        next_retry_at=datetime.now(timezone.utc) + timedelta(seconds=delay),
    )
    # Also record the failed attempt for history.
    failed_row = AuditWebhookDelivery(
        webhook_id=webhook.id,
        audit_event_id=event_id,
        attempt_number=failed_attempt,
        status=STATUS_FAILED,
        http_status_code=http_status,
        error_message=error,
        response_snippet=snippet,
        next_retry_at=None,
    )
    db.add(failed_row)
    db.add(pending)
    _update_webhook_last(db, webhook, status_code=http_status, error=error)
    db.commit()


def execute_delivery_attempt(
    db: Session,
    *,
    webhook: AuditWebhook,
    event: AuditEvent,
    attempt_number: int,
    delivery_id: UUID | None = None,
) -> str:
    """
    Perform one HTTP delivery attempt and persist outcome.

    If delivery_id is set, update that pending row; otherwise create new rows.
    Returns final status for this attempt path: success | failed | exhausted | pending.
    """
    http_status, error, snippet = _http_post(webhook, event)
    now = datetime.now(timezone.utc)

    if error is None and http_status is not None and 200 <= http_status < 300:
        if delivery_id is not None:
            row = db.scalar(
                select(AuditWebhookDelivery).where(AuditWebhookDelivery.id == delivery_id)
            )
            if row is not None:
                row.status = STATUS_SUCCESS
                row.http_status_code = http_status
                row.error_message = None
                row.response_snippet = snippet
                row.next_retry_at = None
                row.attempt_number = attempt_number
                db.add(row)
        else:
            db.add(
                AuditWebhookDelivery(
                    webhook_id=webhook.id,
                    audit_event_id=event.id,
                    attempt_number=attempt_number,
                    status=STATUS_SUCCESS,
                    http_status_code=http_status,
                    error_message=None,
                    response_snippet=snippet,
                    next_retry_at=None,
                )
            )
        _update_webhook_last(db, webhook, status_code=http_status, error=None)
        db.commit()
        return STATUS_SUCCESS

    # Failure path
    settings = get_settings()
    max_attempts = max(1, settings.webhook_max_attempts)

    if delivery_id is not None:
        row = db.scalar(
            select(AuditWebhookDelivery).where(AuditWebhookDelivery.id == delivery_id)
        )
        if row is not None:
            if attempt_number >= max_attempts:
                row.status = STATUS_EXHAUSTED
                row.next_retry_at = None
            else:
                row.status = STATUS_FAILED
                row.next_retry_at = None
            row.http_status_code = http_status
            row.error_message = error
            row.response_snippet = snippet
            row.attempt_number = attempt_number
            db.add(row)

        if attempt_number < max_attempts:
            delay = _backoff_seconds(attempt_number)
            db.add(
                AuditWebhookDelivery(
                    webhook_id=webhook.id,
                    audit_event_id=event.id,
                    attempt_number=attempt_number + 1,
                    status=STATUS_PENDING,
                    http_status_code=http_status,
                    error_message=error,
                    response_snippet=snippet,
                    next_retry_at=now + timedelta(seconds=delay),
                )
            )
            _update_webhook_last(db, webhook, status_code=http_status, error=error)
            db.commit()
            return STATUS_PENDING

        _update_webhook_last(db, webhook, status_code=http_status, error=error)
        db.commit()
        return STATUS_EXHAUSTED

    _schedule_retry_or_exhaust(
        db,
        webhook=webhook,
        event_id=event.id,
        failed_attempt=attempt_number,
        http_status=http_status,
        error=error,
        snippet=snippet,
    )
    return STATUS_EXHAUSTED if attempt_number >= max_attempts else STATUS_PENDING


def _deliver_one(webhook_id: UUID, event_id: UUID, attempt_number: int = 1) -> None:
    """Background first-attempt delivery using a dedicated DB session."""
    db = SessionLocal()
    try:
        webhook = db.scalar(select(AuditWebhook).where(AuditWebhook.id == webhook_id))
        event = db.scalar(select(AuditEvent).where(AuditEvent.id == event_id))
        if webhook is None or event is None or not webhook.is_active:
            return
        if not _matches_filters(webhook, event.action):
            return
        execute_delivery_attempt(
            db,
            webhook=webhook,
            event=event,
            attempt_number=attempt_number,
            delivery_id=None,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Webhook delivery worker failed webhook_id=%s", webhook_id)
    finally:
        db.close()


def process_due_retries(limit: int = 50) -> int:
    """Process pending deliveries whose next_retry_at has passed. Returns count processed."""
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    processed = 0
    try:
        pending = db.scalars(
            select(AuditWebhookDelivery)
            .where(
                AuditWebhookDelivery.status == STATUS_PENDING,
                AuditWebhookDelivery.next_retry_at.is_not(None),
                AuditWebhookDelivery.next_retry_at <= now,
            )
            .order_by(AuditWebhookDelivery.next_retry_at.asc())
            .limit(limit)
        ).all()

        for delivery in pending:
            webhook = db.scalar(
                select(AuditWebhook).where(AuditWebhook.id == delivery.webhook_id)
            )
            event = (
                db.scalar(select(AuditEvent).where(AuditEvent.id == delivery.audit_event_id))
                if delivery.audit_event_id
                else None
            )
            if webhook is None or event is None or not webhook.is_active:
                delivery.status = STATUS_EXHAUSTED
                delivery.error_message = (
                    delivery.error_message or "Webhook inactive or event missing"
                )
                delivery.next_retry_at = None
                db.add(delivery)
                db.commit()
                processed += 1
                continue

            execute_delivery_attempt(
                db,
                webhook=webhook,
                event=event,
                attempt_number=delivery.attempt_number,
                delivery_id=delivery.id,
            )
            processed += 1
    except Exception:  # noqa: BLE001
        logger.exception("Webhook retry sweep failed")
    finally:
        db.close()
    return processed


def dispatch_webhooks_for_event(
    *,
    event_id: UUID,
    organization_id: UUID,
    action: str,
) -> None:
    """
    Fan out an audit event to matching org webhooks (async threads).
    Skips webhook.* actions to avoid recursion.
    """
    if action.startswith("webhooks."):
        return

    db = SessionLocal()
    try:
        rows = db.scalars(
            select(AuditWebhook).where(
                AuditWebhook.organization_id == organization_id,
                AuditWebhook.is_active.is_(True),
            )
        ).all()
        targets = [row.id for row in rows if _matches_filters(row, action)]
    finally:
        db.close()

    for webhook_id in targets:
        thread = threading.Thread(
            target=_deliver_one,
            args=(webhook_id, event_id, 1),
            daemon=True,
            name=f"webhook-{webhook_id}",
        )
        thread.start()


def test_webhook(db: Session, *, actor: User, webhook_id: UUID) -> WebhookResponse:
    """Send a synthetic ping event to the webhook (synchronous for UI feedback)."""
    row = db.scalar(
        select(AuditWebhook)
        .options(joinedload(AuditWebhook.organization))
        .where(AuditWebhook.id == webhook_id)
    )
    if row is None:
        raise NotFoundError("Webhook not found")
    require_organization_access(db, row.organization.slug, actor=actor)

    from app.services.audit_service import record_event

    event_id = record_event(
        action="webhooks.test",
        status="success",
        organization_id=row.organization_id,
        actor=actor,
        resource_type="audit_webhook",
        resource_id=str(row.id),
        summary=f"Test delivery for webhook “{row.name}”",
        details={"url": row.url},
    )
    if event_id is not None:
        # webhooks.* skips auto-dispatch; deliver synchronously for immediate status.
        _deliver_one(row.id, event_id, 1)

    db.expire_all()
    row = db.scalar(
        select(AuditWebhook)
        .options(joinedload(AuditWebhook.organization))
        .where(AuditWebhook.id == webhook_id)
    )
    assert row is not None
    return webhook_to_response(row)
