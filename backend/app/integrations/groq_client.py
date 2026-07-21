"""
Groq client (OpenAI-compatible Chat Completions API).

Why Groq:
- Generous free tier for Arena demos.
- Same request shape as OpenAI via base_url override.
"""

from __future__ import annotations

import time

from openai import APIError, AuthenticationError, OpenAI, RateLimitError

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.integrations.base import ProviderCompletionResult
from app.integrations.openai_stream import stream_openai_compatible

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqClient:
    """Thin wrapper around Groq's OpenAI-compatible API."""

    provider = "groq"

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        key = api_key if api_key is not None else settings.groq_api_key
        if not key:
            raise AppException(
                "Groq API key is not configured. Set GROQ_API_KEY in backend/.env",
                code="groq_not_configured",
                status_code=503,
            )
        self._client = OpenAI(api_key=key, base_url=GROQ_BASE_URL)

    def complete(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> ProviderCompletionResult:
        started = time.perf_counter()
        try:
            completion = self._client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except AuthenticationError as exc:
            raise AppException(
                "Groq authentication failed. Check GROQ_API_KEY.",
                code="groq_auth_error",
                status_code=401,
                details={"provider": "groq"},
            ) from exc
        except RateLimitError as exc:
            raise AppException(
                "Groq rate limit exceeded. Retry shortly.",
                code="groq_rate_limit",
                status_code=429,
                details={"provider": "groq"},
            ) from exc
        except APIError as exc:
            message = getattr(exc, "message", None) or str(exc)
            raise AppException(
                f"Groq API error: {message}",
                code="groq_api_error",
                status_code=502,
                details={"provider": "groq"},
            ) from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        choice = completion.choices[0].message.content or ""
        usage = completion.usage

        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else prompt_tokens + completion_tokens

        return ProviderCompletionResult(
            provider=self.provider,
            model=completion.model or model,
            response_text=choice,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
        )

    def complete_stream(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ):
        """Yield text deltas, then a final ProviderCompletionResult."""
        return stream_openai_compatible(
            self._client,
            provider=self.provider,
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
