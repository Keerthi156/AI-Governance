"""
LLM orchestration service.

Why this exists:
- Routes stay thin: validate → call service → return schema.
- Owns the full lifecycle: provider call, cost estimate, prompt_history persist.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppException, ValidationAppError
from app.models.prompt_history import PromptHistory
from app.services.cost_estimator import estimate_cost_usd
from app.services.governance_service import assert_request_allowed
from app.services.organization_service import get_or_create_organization
from app.services.provider_credential_service import resolve_provider_api_key
from app.services.provider_registry import (
    SUPPORTED_PROVIDERS,
    call_provider,
    call_provider_stream,
    resolve_model,
)


@dataclass(frozen=True)
class CompletionOutcome:
    """Result returned to the API layer after a completion attempt."""

    history_id: str
    provider: str
    model: str
    prompt: str
    response: str | None
    status: str
    error_message: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    estimated_cost_usd: Decimal | None
    latency_ms: int | None
    organization_slug: str
    arena_run_id: str | None = None


def _validate_completion_input(
    *,
    provider: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
) -> tuple[str, str]:
    provider_key = provider.strip().lower()
    if provider_key not in SUPPORTED_PROVIDERS:
        raise ValidationAppError(
            f"Unsupported provider '{provider}'. Supported: {sorted(SUPPORTED_PROVIDERS)}",
            details={"provider": provider},
        )

    cleaned_prompt = prompt.strip()
    if not cleaned_prompt:
        raise ValidationAppError("Prompt must not be empty.")

    if temperature < 0 or temperature > 2:
        raise ValidationAppError("temperature must be between 0 and 2.")

    if max_tokens < 1 or max_tokens > 8192:
        raise ValidationAppError("max_tokens must be between 1 and 8192.")

    return provider_key, cleaned_prompt


def run_completion(
    db: Session,
    *,
    provider: str,
    prompt: str,
    model: str | None = None,
    organization_slug: str = "default",
    temperature: float = 0.7,
    max_tokens: int = 1024,
    arena_run_id: UUID | None = None,
    raise_on_error: bool = True,
    enforce_policies: bool = True,
    policy_prompt: str | None = None,
) -> CompletionOutcome:
    """
    Execute an LLM completion and persist the attempt to prompt_history.

    Failed provider calls are still saved with status=error for auditability.
    When raise_on_error=False (Arena Mode), returns the error outcome instead.

    policy_prompt: optional text used for governance checks (defaults to prompt).
    Set enforce_policies=False only when the caller already enforced policies.
    """
    provider_key, cleaned_prompt = _validate_completion_input(
        provider=provider,
        prompt=prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    resolved_model = resolve_model(provider_key, model)
    org = get_or_create_organization(db, slug=organization_slug)

    if enforce_policies:
        # Prefer user-facing text for an early deny; always sanitize the outbound prompt.
        if policy_prompt is not None:
            assert_request_allowed(
                db,
                organization_id=org.id,
                provider=provider_key,
                model=resolved_model,
                prompt=policy_prompt,
                max_tokens=max_tokens,
            )
        cleaned_prompt = assert_request_allowed(
            db,
            organization_id=org.id,
            provider=provider_key,
            model=resolved_model,
            prompt=cleaned_prompt,
            max_tokens=max_tokens,
        )

    history = PromptHistory(
        organization_id=org.id,
        provider=provider_key,
        model=resolved_model,
        prompt=cleaned_prompt,
        status="pending",
        arena_run_id=arena_run_id,
    )
    db.add(history)
    db.commit()
    db.refresh(history)

    try:
        result = call_provider(
            provider=provider_key,
            prompt=cleaned_prompt,
            model=resolved_model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=resolve_provider_api_key(
                db, organization_id=org.id, provider=provider_key
            ),
        )
        cost = estimate_cost_usd(
            resolved_model,
            result.prompt_tokens,
            result.completion_tokens,
        )

        history.response = result.response_text
        history.status = "success"
        history.prompt_tokens = result.prompt_tokens
        history.completion_tokens = result.completion_tokens
        history.total_tokens = result.total_tokens
        history.estimated_cost_usd = cost
        history.latency_ms = result.latency_ms
        history.model = result.model
        db.commit()
        db.refresh(history)

        return CompletionOutcome(
            history_id=str(history.id),
            provider=history.provider,
            model=history.model,
            prompt=history.prompt,
            response=history.response,
            status=history.status,
            error_message=None,
            prompt_tokens=history.prompt_tokens,
            completion_tokens=history.completion_tokens,
            total_tokens=history.total_tokens,
            estimated_cost_usd=history.estimated_cost_usd,
            latency_ms=history.latency_ms,
            organization_slug=org.slug,
            arena_run_id=str(arena_run_id) if arena_run_id else None,
        )
    except AppException as exc:
        history.status = "error"
        history.error_message = exc.message
        db.commit()
        db.refresh(history)
        if raise_on_error:
            raise
        return CompletionOutcome(
            history_id=str(history.id),
            provider=history.provider,
            model=history.model,
            prompt=history.prompt,
            response=None,
            status=history.status,
            error_message=history.error_message,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            estimated_cost_usd=None,
            latency_ms=None,
            organization_slug=org.slug,
            arena_run_id=str(arena_run_id) if arena_run_id else None,
        )
    except Exception as exc:  # noqa: BLE001
        history.status = "error"
        history.error_message = str(exc)
        db.commit()
        if raise_on_error:
            raise AppException(
                "Unexpected error while running completion",
                code="completion_failed",
                status_code=500,
            ) from exc
        db.refresh(history)
        return CompletionOutcome(
            history_id=str(history.id),
            provider=history.provider,
            model=history.model,
            prompt=history.prompt,
            response=None,
            status=history.status,
            error_message=history.error_message,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            estimated_cost_usd=None,
            latency_ms=None,
            organization_slug=org.slug,
            arena_run_id=str(arena_run_id) if arena_run_id else None,
        )


def run_completion_stream(
    db: Session,
    *,
    provider: str,
    prompt: str,
    model: str | None = None,
    organization_slug: str = "default",
    temperature: float = 0.7,
    max_tokens: int = 1024,
    policy_prompt: str | None = None,
):
    """
    Stream a playground completion.

    Yields dict events: meta → token* → done | error.
    """
    from app.integrations.base import ProviderCompletionResult

    provider_key, cleaned_prompt = _validate_completion_input(
        provider=provider,
        prompt=prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    resolved_model = resolve_model(provider_key, model)
    org = get_or_create_organization(db, slug=organization_slug)

    if policy_prompt is not None:
        assert_request_allowed(
            db,
            organization_id=org.id,
            provider=provider_key,
            model=resolved_model,
            prompt=policy_prompt,
            max_tokens=max_tokens,
        )
    cleaned_prompt = assert_request_allowed(
        db,
        organization_id=org.id,
        provider=provider_key,
        model=resolved_model,
        prompt=cleaned_prompt,
        max_tokens=max_tokens,
    )

    history = PromptHistory(
        organization_id=org.id,
        provider=provider_key,
        model=resolved_model,
        prompt=cleaned_prompt,
        status="pending",
    )
    db.add(history)
    db.commit()
    db.refresh(history)

    yield {
        "type": "meta",
        "history_id": str(history.id),
        "provider": provider_key,
        "model": resolved_model,
        "organization_slug": org.slug,
    }

    try:
        final: ProviderCompletionResult | None = None
        for item in call_provider_stream(
            provider=provider_key,
            prompt=cleaned_prompt,
            model=resolved_model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=resolve_provider_api_key(
                db, organization_id=org.id, provider=provider_key
            ),
        ):
            if isinstance(item, str):
                yield {"type": "token", "text": item}
            else:
                final = item

        if final is None:
            raise AppException(
                "Stream ended without a completion result",
                code="completion_failed",
                status_code=500,
            )

        cost = estimate_cost_usd(
            resolved_model,
            final.prompt_tokens,
            final.completion_tokens,
        )
        history.response = final.response_text
        history.status = "success"
        history.prompt_tokens = final.prompt_tokens
        history.completion_tokens = final.completion_tokens
        history.total_tokens = final.total_tokens
        history.estimated_cost_usd = cost
        history.latency_ms = final.latency_ms
        history.model = final.model
        db.commit()
        db.refresh(history)

        yield {
            "type": "done",
            "history_id": str(history.id),
            "provider": history.provider,
            "model": history.model,
            "prompt": history.prompt,
            "response": history.response,
            "status": history.status,
            "error_message": None,
            "prompt_tokens": history.prompt_tokens,
            "completion_tokens": history.completion_tokens,
            "total_tokens": history.total_tokens,
            "estimated_cost_usd": (
                str(history.estimated_cost_usd)
                if history.estimated_cost_usd is not None
                else None
            ),
            "latency_ms": history.latency_ms,
            "organization_slug": org.slug,
            "arena_run_id": None,
        }
    except AppException as exc:
        history.status = "error"
        history.error_message = exc.message
        db.commit()
        yield {
            "type": "error",
            "message": exc.message,
            "code": exc.code,
            "history_id": str(history.id),
        }
    except Exception as exc:  # noqa: BLE001
        history.status = "error"
        history.error_message = str(exc)
        db.commit()
        yield {
            "type": "error",
            "message": str(exc),
            "code": "completion_failed",
            "history_id": str(history.id),
        }
