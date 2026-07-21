"""
Background retention scheduler — periodic purge for opted-in organizations.

Why this exists:
- Manual purge alone does not meet continuous retention SLAs.
- Opt-in per org keeps deletes explicit; the daemon only touches enrolled tenants.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.audit_service import record_event
from app.services.retention_service import (
    list_auto_purge_organizations,
    purge_expired_for_organization,
)

logger = logging.getLogger("app.retention.scheduler")

SYSTEM_ACTOR_EMAIL = "system:retention-scheduler"


@dataclass
class RetentionSchedulerState:
    enabled: bool = False
    interval_seconds: int = 3600
    initial_delay_seconds: int = 30
    thread_alive: bool = False
    last_cycle_started_at: datetime | None = None
    last_cycle_finished_at: datetime | None = None
    last_error: str | None = None
    last_orgs_processed: int = 0
    last_prompt_history_deleted: int = 0
    last_audit_events_deleted: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": self.enabled,
                "interval_seconds": self.interval_seconds,
                "initial_delay_seconds": self.initial_delay_seconds,
                "thread_alive": self.thread_alive,
                "last_cycle_started_at": self.last_cycle_started_at,
                "last_cycle_finished_at": self.last_cycle_finished_at,
                "last_error": self.last_error,
                "last_orgs_processed": self.last_orgs_processed,
                "last_prompt_history_deleted": self.last_prompt_history_deleted,
                "last_audit_events_deleted": self.last_audit_events_deleted,
            }


_state = RetentionSchedulerState()
_stop_event: threading.Event | None = None
_thread: threading.Thread | None = None


def get_scheduler_state() -> RetentionSchedulerState:
    return _state


def run_purge_cycle() -> dict[str, Any]:
    """
    Purge expired rows for every org with auto-purge enabled.

    Safe to call from tests or the daemon thread.
    """
    started = datetime.now(timezone.utc)
    with _state._lock:
        _state.last_cycle_started_at = started
        _state.last_error = None

    orgs_processed = 0
    prompt_deleted = 0
    audit_deleted = 0

    db = SessionLocal()
    try:
        orgs = list_auto_purge_organizations(db)
        for org in orgs:
            # Skip orgs with no retention windows configured.
            if (
                org.prompt_history_retention_days is None
                and org.audit_events_retention_days is None
            ):
                continue
            result = purge_expired_for_organization(db, org, dry_run=False)
            org.retention_last_auto_purge_at = datetime.now(timezone.utc)
            db.add(org)
            db.commit()
            orgs_processed += 1
            prompt_deleted += result.prompt_history_deleted
            audit_deleted += result.audit_events_deleted
            record_event(
                action="retention.purge.scheduled",
                status="success",
                organization_id=org.id,
                actor_email=SYSTEM_ACTOR_EMAIL,
                resource_type="organization",
                resource_id=str(org.id),
                summary=(
                    f"Scheduled purge {org.slug}: "
                    f"history={result.prompt_history_deleted} "
                    f"audit={result.audit_events_deleted}"
                ),
                details=result.model_dump(mode="json"),
            )
    except Exception as exc:  # noqa: BLE001 — daemon must not crash silently without record
        logger.exception("Retention scheduler cycle failed")
        with _state._lock:
            _state.last_error = str(exc)
        raise
    finally:
        db.close()

    finished = datetime.now(timezone.utc)
    with _state._lock:
        _state.last_cycle_finished_at = finished
        _state.last_orgs_processed = orgs_processed
        _state.last_prompt_history_deleted = prompt_deleted
        _state.last_audit_events_deleted = audit_deleted

    summary = {
        "orgs_processed": orgs_processed,
        "prompt_history_deleted": prompt_deleted,
        "audit_events_deleted": audit_deleted,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
    }
    logger.info("Retention scheduler cycle complete: %s", summary)
    return summary


def _loop(stop_event: threading.Event) -> None:
    settings = get_settings()
    if stop_event.wait(settings.retention_scheduler_initial_delay_seconds):
        return
    while not stop_event.is_set():
        try:
            run_purge_cycle()
        except Exception:  # noqa: BLE001
            # Error already logged + stored on state; keep looping.
            pass
        if stop_event.wait(settings.retention_scheduler_interval_seconds):
            break


def start_retention_scheduler() -> threading.Thread | None:
    """Start the daemon thread when enabled. Idempotent."""
    global _stop_event, _thread

    settings = get_settings()
    with _state._lock:
        _state.enabled = settings.retention_scheduler_enabled
        _state.interval_seconds = settings.retention_scheduler_interval_seconds
        _state.initial_delay_seconds = settings.retention_scheduler_initial_delay_seconds

    if not settings.retention_scheduler_enabled:
        logger.info("Retention scheduler disabled via settings")
        return None

    if _thread is not None and _thread.is_alive():
        return _thread

    _stop_event = threading.Event()
    _thread = threading.Thread(
        target=_loop,
        args=(_stop_event,),
        name="retention-scheduler",
        daemon=True,
    )
    _thread.start()
    with _state._lock:
        _state.thread_alive = True
    logger.info(
        "Retention scheduler started (interval=%ss, initial_delay=%ss)",
        settings.retention_scheduler_interval_seconds,
        settings.retention_scheduler_initial_delay_seconds,
    )
    return _thread


def stop_retention_scheduler(timeout: float = 5.0) -> None:
    """Signal the daemon to stop and join briefly."""
    global _stop_event, _thread
    if _stop_event is not None:
        _stop_event.set()
    if _thread is not None:
        _thread.join(timeout=timeout)
    with _state._lock:
        _state.thread_alive = bool(_thread and _thread.is_alive())
    _thread = None
    _stop_event = None
