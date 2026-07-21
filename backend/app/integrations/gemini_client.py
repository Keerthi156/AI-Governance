"""
Google Gemini client via the Generative Language REST API (httpx).

Why httpx instead of a heavy SDK:
- Keeps dependencies lean while supporting Arena Mode.
- Same normalized ProviderCompletionResult as OpenAI/Claude.
"""

from __future__ import annotations

import time

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.integrations.base import ProviderCompletionResult

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiClient:
    """Gemini generateContent adapter."""

    provider = "gemini"

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        key = api_key if api_key is not None else settings.google_api_key
        if not key:
            raise AppException(
                "Google API key is not configured. Set GOOGLE_API_KEY in backend/.env",
                code="gemini_not_configured",
                status_code=503,
            )
        self._api_key = key

    def complete(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> ProviderCompletionResult:
        started = time.perf_counter()
        url = f"{GEMINI_BASE}/models/{model}:generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    url,
                    params={"key": self._api_key},
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise AppException(
                f"Gemini network error: {exc}",
                code="gemini_network_error",
                status_code=502,
                details={"provider": "gemini"},
            ) from exc

        latency_ms = int((time.perf_counter() - started) * 1000)

        if response.status_code == 401 or response.status_code == 403:
            raise AppException(
                "Gemini authentication failed. Check GOOGLE_API_KEY.",
                code="gemini_auth_error",
                status_code=401,
                details={"provider": "gemini"},
            )
        if response.status_code == 429:
            detail = response.text[:300]
            raise AppException(
                f"Gemini rate limit or quota issue. Detail: {detail}",
                code="gemini_rate_limit",
                status_code=429,
                details={"provider": "gemini"},
            )
        if response.status_code >= 400:
            detail = response.text[:500]
            raise AppException(
                f"Gemini API error: {detail}",
                code="gemini_api_error",
                status_code=502,
                details={"provider": "gemini"},
            )

        data = response.json()
        candidates = data.get("candidates") or []
        text = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts") or []
            text = "\n".join(part.get("text", "") for part in parts if part.get("text"))

        usage = data.get("usageMetadata") or {}
        prompt_tokens = int(usage.get("promptTokenCount") or 0)
        completion_tokens = int(usage.get("candidatesTokenCount") or 0)
        total_tokens = int(usage.get("totalTokenCount") or (prompt_tokens + completion_tokens))

        return ProviderCompletionResult(
            provider=self.provider,
            model=model,
            response_text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
        )
