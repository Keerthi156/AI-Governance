"""
Anthropic Claude Messages client.
"""

from __future__ import annotations

import time

from anthropic import APIError, Anthropic, AuthenticationError, RateLimitError

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.integrations.base import ProviderCompletionResult


class ClaudeClient:
    """Thin wrapper around the Anthropic Python SDK."""

    provider = "claude"

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        key = api_key if api_key is not None else settings.anthropic_api_key
        if not key:
            raise AppException(
                "Anthropic API key is not configured. Set ANTHROPIC_API_KEY in backend/.env",
                code="claude_not_configured",
                status_code=503,
            )
        self._client = Anthropic(api_key=key)

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
            message = self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
        except AuthenticationError as exc:
            raise AppException(
                "Anthropic authentication failed. Check ANTHROPIC_API_KEY.",
                code="claude_auth_error",
                status_code=401,
                details={"provider": "claude"},
            ) from exc
        except RateLimitError as exc:
            raise AppException(
                "Anthropic rate limit exceeded. Retry shortly.",
                code="claude_rate_limit",
                status_code=429,
                details={"provider": "claude"},
            ) from exc
        except APIError as exc:
            message = getattr(exc, "message", None) or str(exc)
            raise AppException(
                f"Anthropic API error: {message}",
                code="claude_api_error",
                status_code=502,
                details={"provider": "claude"},
            ) from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        text_parts = [
            block.text
            for block in message.content
            if getattr(block, "type", None) == "text" and hasattr(block, "text")
        ]
        response_text = "\n".join(text_parts)

        usage = message.usage
        prompt_tokens = getattr(usage, "input_tokens", 0) or 0
        completion_tokens = getattr(usage, "output_tokens", 0) or 0

        return ProviderCompletionResult(
            provider=self.provider,
            model=message.model or model,
            response_text=response_text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
        )
