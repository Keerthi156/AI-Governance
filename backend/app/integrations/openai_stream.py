"""
Shared helper for OpenAI-compatible streaming (OpenAI + Groq).
"""

from __future__ import annotations

import time
from collections.abc import Iterator

from openai import APIError, AuthenticationError, OpenAI, RateLimitError

from app.core.exceptions import AppException
from app.integrations.base import ProviderCompletionResult


def stream_openai_compatible(
    client: OpenAI,
    *,
    provider: str,
    prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> Iterator[str | ProviderCompletionResult]:
    """
    Yield text deltas (str), then a final ProviderCompletionResult.

    Token counts: prefer stream usage when available; else estimate from text.
    """
    started = time.perf_counter()
    try:
        stream = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
    except TypeError:
        # Older SDK / provider may not accept stream_options.
        stream = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
    except AuthenticationError as exc:
        raise AppException(
            f"{provider} authentication failed. Check API key.",
            code=f"{provider}_auth_error",
            status_code=401,
            details={"provider": provider},
        ) from exc
    except RateLimitError as exc:
        raise AppException(
            f"{provider} rate limit exceeded. Retry shortly.",
            code=f"{provider}_rate_limit",
            status_code=429,
            details={"provider": provider},
        ) from exc
    except APIError as exc:
        message = getattr(exc, "message", None) or str(exc)
        raise AppException(
            f"{provider} API error: {message}",
            code=f"{provider}_api_error",
            status_code=502,
            details={"provider": provider},
        ) from exc

    parts: list[str] = []
    resolved_model = model
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0

    try:
        for chunk in stream:
            if getattr(chunk, "model", None):
                resolved_model = chunk.model or resolved_model
            usage = getattr(chunk, "usage", None)
            if usage is not None:
                prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
                completion_tokens = getattr(usage, "completion_tokens", 0) or 0
                total_tokens = getattr(usage, "total_tokens", 0) or (
                    prompt_tokens + completion_tokens
                )
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            text = getattr(delta, "content", None) if delta is not None else None
            if text:
                parts.append(text)
                yield text
    except APIError as exc:
        message = getattr(exc, "message", None) or str(exc)
        raise AppException(
            f"{provider} API error: {message}",
            code=f"{provider}_api_error",
            status_code=502,
            details={"provider": provider},
        ) from exc

    response_text = "".join(parts)
    latency_ms = int((time.perf_counter() - started) * 1000)
    if total_tokens <= 0:
        # Rough fallback when usage is not included on the stream.
        prompt_tokens = max(1, len(prompt.split()))
        completion_tokens = max(0, len(response_text.split()))
        total_tokens = prompt_tokens + completion_tokens

    yield ProviderCompletionResult(
        provider=provider,
        model=resolved_model,
        response_text=response_text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        latency_ms=latency_ms,
    )
