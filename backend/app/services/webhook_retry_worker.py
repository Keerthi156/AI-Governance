"""
Background worker that retries pending webhook deliveries.

Why this exists:
- First-attempt threads may fail transiently; durable pending rows need a sweeper.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.services.webhook_service import process_due_retries

logger = logging.getLogger("app.webhooks.retry")


@dataclass
class WebhookRetryWorkerState:
    enabled: bool = False
    interval_seconds: int = 15
    initial_delay_seconds: int = 10
    thread_alive: bool = False
    last_cycle_at: datetime | None = None
    last_processed: int = 0
    last_error: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": self.enabled,
                "interval_seconds": self.interval_seconds,
                "initial_delay_seconds": self.initial_delay_seconds,
                "thread_alive": self.thread_alive,
                "last_cycle_at": self.last_cycle_at,
                "last_processed": self.last_processed,
                "last_error": self.last_error,
            }


_state = WebhookRetryWorkerState()
_stop_event: threading.Event | None = None
_thread: threading.Thread | None = None


def get_retry_worker_state() -> WebhookRetryWorkerState:
    return _state


def _loop(stop_event: threading.Event) -> None:
    settings = get_settings()
    if stop_event.wait(settings.webhook_retry_worker_initial_delay_seconds):
        return
    while not stop_event.is_set():
        try:
            processed = process_due_retries()
            with _state._lock:
                _state.last_cycle_at = datetime.now(timezone.utc)
                _state.last_processed = processed
                _state.last_error = None
            if processed:
                logger.info("Webhook retry worker processed %s deliveries", processed)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Webhook retry worker cycle failed")
            with _state._lock:
                _state.last_error = str(exc)
        if stop_event.wait(settings.webhook_retry_worker_interval_seconds):
            break


def start_webhook_retry_worker() -> threading.Thread | None:
    global _stop_event, _thread

    settings = get_settings()
    with _state._lock:
        _state.enabled = settings.webhook_retry_worker_enabled
        _state.interval_seconds = settings.webhook_retry_worker_interval_seconds
        _state.initial_delay_seconds = settings.webhook_retry_worker_initial_delay_seconds

    if not settings.webhook_retry_worker_enabled:
        logger.info("Webhook retry worker disabled via settings")
        return None

    if _thread is not None and _thread.is_alive():
        return _thread

    _stop_event = threading.Event()
    _thread = threading.Thread(
        target=_loop,
        args=(_stop_event,),
        name="webhook-retry-worker",
        daemon=True,
    )
    _thread.start()
    with _state._lock:
        _state.thread_alive = True
    logger.info(
        "Webhook retry worker started (interval=%ss)",
        settings.webhook_retry_worker_interval_seconds,
    )
    return _thread


def stop_webhook_retry_worker(timeout: float = 5.0) -> None:
    global _stop_event, _thread
    if _stop_event is not None:
        _stop_event.set()
    if _thread is not None:
        _thread.join(timeout=timeout)
    with _state._lock:
        _state.thread_alive = bool(_thread and _thread.is_alive())
    _thread = None
    _stop_event = None
