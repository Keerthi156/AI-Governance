"""
Arena Mode orchestration.

Why this exists:
- Runs the same prompt across multiple provider/model pairs.
- Groups results under one arena_run_id for comparison + analytics.
- Provider calls run in parallel; DB writes stay on the request thread.
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import AppException, ValidationAppError
from app.models.prompt_history import PromptHistory
from app.services.cost_estimator import estimate_cost_usd
from app.services.governance_service import assert_request_allowed
from app.services.llm_service import CompletionOutcome
from app.services.organization_service import get_or_create_organization
from app.services.provider_credential_service import resolve_provider_api_key
from app.services.provider_registry import (
    SUPPORTED_PROVIDERS,
    call_provider,
    resolve_model,
)


@dataclass(frozen=True)
class ArenaParticipant:
    provider: str
    model: str | None = None


@dataclass(frozen=True)
class ArenaRunOutcome:
    arena_run_id: str
    prompt: str
    organization_slug: str
    results: list[CompletionOutcome]
    total_estimated_cost_usd: Decimal | None
    success_count: int
    error_count: int


def _provider_call_only(
    *,
    provider: str,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    api_key: str | None = None,
) -> tuple[str, object]:
    """Execute provider call off the main thread. Returns (provider, result|exception)."""
    try:
        result = call_provider(
            provider=provider,
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
        )
        return provider, result
    except Exception as exc:  # noqa: BLE001 - captured per participant
        return provider, exc


def run_arena(
    db: Session,
    *,
    prompt: str,
    participants: list[ArenaParticipant],
    organization_slug: str = "default",
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> ArenaRunOutcome:
    """
    Fan out one prompt to multiple models and persist linked history rows.
    """
    cleaned_prompt = prompt.strip()
    if not cleaned_prompt:
        raise ValidationAppError("Prompt must not be empty.")

    if len(participants) < 2:
        raise ValidationAppError("Arena requires at least 2 participants.")

    if len(participants) > 6:
        raise ValidationAppError("Arena supports at most 6 participants.")

    if temperature < 0 or temperature > 2:
        raise ValidationAppError("temperature must be between 0 and 2.")

    if max_tokens < 1 or max_tokens > 8192:
        raise ValidationAppError("max_tokens must be between 1 and 8192.")

    normalized: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for participant in participants:
        provider = participant.provider.strip().lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise ValidationAppError(
                f"Unsupported provider '{participant.provider}'. "
                f"Supported: {sorted(SUPPORTED_PROVIDERS)}"
            )
        model = resolve_model(provider, participant.model)
        key = (provider, model)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(key)

    if len(normalized) < 2:
        raise ValidationAppError(
            "Arena requires at least 2 unique provider/model pairs."
        )

    org = get_or_create_organization(db, slug=organization_slug)
    arena_run_id = uuid.uuid4()

    # Enforce policies for the shared prompt/tokens and each participant.
    sanitized_prompt = cleaned_prompt
    for provider, model in normalized:
        sanitized_prompt = assert_request_allowed(
            db,
            organization_id=org.id,
            provider=provider,
            model=model,
            prompt=cleaned_prompt,
            max_tokens=max_tokens,
        )
    cleaned_prompt = sanitized_prompt

    # Create pending rows first so every attempt is auditable.
    history_by_key: dict[tuple[str, str], PromptHistory] = {}
    for provider, model in normalized:
        row = PromptHistory(
            organization_id=org.id,
            provider=provider,
            model=model,
            prompt=cleaned_prompt,
            status="pending",
            arena_run_id=arena_run_id,
        )
        db.add(row)
        history_by_key[(provider, model)] = row
    db.commit()
    for row in history_by_key.values():
        db.refresh(row)

    # Parallel provider calls (no shared SQLAlchemy session across threads).
    # Resolve BYOK keys on the main thread before fan-out.
    api_keys = {
        provider: resolve_provider_api_key(
            db, organization_id=org.id, provider=provider
        )
        for provider, _model in normalized
    }
    call_results: dict[tuple[str, str], object] = {}
    with ThreadPoolExecutor(max_workers=min(6, len(normalized))) as pool:
        futures = {
            pool.submit(
                _provider_call_only,
                provider=provider,
                model=model,
                prompt=cleaned_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=api_keys.get(provider),
            ): (provider, model)
            for provider, model in normalized
        }
        for future in as_completed(futures):
            key = futures[future]
            _, payload = future.result()
            call_results[key] = payload

    outcomes: list[CompletionOutcome] = []
    success_count = 0
    error_count = 0
    cost_total = Decimal("0")
    cost_known = False

    for provider, model in normalized:
        history = history_by_key[(provider, model)]
        payload = call_results[(provider, model)]

        if isinstance(payload, Exception):
            message = (
                payload.message
                if isinstance(payload, AppException)
                else str(payload)
            )
            history.status = "error"
            history.error_message = message
            error_count += 1
            db.add(history)
            outcomes.append(
                CompletionOutcome(
                    history_id=str(history.id),
                    provider=provider,
                    model=model,
                    prompt=cleaned_prompt,
                    response=None,
                    status="error",
                    error_message=message,
                    prompt_tokens=None,
                    completion_tokens=None,
                    total_tokens=None,
                    estimated_cost_usd=None,
                    latency_ms=None,
                    organization_slug=org.slug,
                    arena_run_id=str(arena_run_id),
                )
            )
            continue

        cost = estimate_cost_usd(
            model,
            payload.prompt_tokens,
            payload.completion_tokens,
        )
        history.response = payload.response_text
        history.status = "success"
        history.prompt_tokens = payload.prompt_tokens
        history.completion_tokens = payload.completion_tokens
        history.total_tokens = payload.total_tokens
        history.estimated_cost_usd = cost
        history.latency_ms = payload.latency_ms
        history.model = payload.model
        db.add(history)
        success_count += 1
        if cost is not None:
            cost_total += cost
            cost_known = True

        outcomes.append(
            CompletionOutcome(
                history_id=str(history.id),
                provider=provider,
                model=payload.model,
                prompt=cleaned_prompt,
                response=payload.response_text,
                status="success",
                error_message=None,
                prompt_tokens=payload.prompt_tokens,
                completion_tokens=payload.completion_tokens,
                total_tokens=payload.total_tokens,
                estimated_cost_usd=cost,
                latency_ms=payload.latency_ms,
                organization_slug=org.slug,
                arena_run_id=str(arena_run_id),
            )
        )

    db.commit()

    return ArenaRunOutcome(
        arena_run_id=str(arena_run_id),
        prompt=cleaned_prompt,
        organization_slug=org.slug,
        results=outcomes,
        total_estimated_cost_usd=cost_total if cost_known else None,
        success_count=success_count,
        error_count=error_count,
    )
