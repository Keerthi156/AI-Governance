"""
HTTP rate limiting middleware (sliding window, in-memory).

Why this exists:
- Soft-protects auth, LLM, and RAG endpoints from burst abuse.
- Returns standard 429 + Retry-After without changing route handlers.
"""

from __future__ import annotations

import hashlib
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.rate_limit import rate_limiter

logger = logging.getLogger("app.rate_limit")

# Paths that should never be rate-limited (probes / docs).
_EXEMPT_SUFFIXES = (
    "/health",
    "/ready",
    "/meta",
    "/docs",
    "/redoc",
    "/openapi.json",
)

_LLM_PREFIXES = (
    "/api/v1/llm",
    "/api/v1/arena",
    "/api/v1/rag/query",
    "/api/v1/agents/runs",
)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _rate_limit_key(request: Request) -> str:
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer ") and len(auth) > 20:
        token = auth.split(" ", 1)[1].strip()
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]
        return f"user:{digest}"
    return f"ip:{_client_ip(request)}"


def _is_exempt(path: str) -> bool:
    return any(path.endswith(suffix) or path == suffix for suffix in _EXEMPT_SUFFIXES)


def _is_llm_heavy(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _LLM_PREFIXES)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply global + stricter LLM window limits when enabled."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path
        if request.method == "OPTIONS" or _is_exempt(path):
            return await call_next(request)

        key = _rate_limit_key(request)
        limit = settings.rate_limit_requests
        window = settings.rate_limit_window_seconds
        scope = "global"

        if _is_llm_heavy(path):
            limit = settings.rate_limit_llm_requests
            window = settings.rate_limit_llm_window_seconds
            scope = "llm"
            key = f"{key}:llm"

        allowed, remaining, retry_after = rate_limiter.check(
            key,
            limit=limit,
            window_seconds=window,
        )

        if not allowed:
            request_id = getattr(request.state, "request_id", None)
            logger.warning(
                "rate_limited scope=%s key=%s path=%s retry_after=%s",
                scope,
                key,
                path,
                retry_after,
            )
            headers = {
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Scope": scope,
            }
            if request_id:
                headers["X-Request-ID"] = str(request_id)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Rate limit exceeded ({scope}). "
                        f"Try again in {retry_after}s."
                    ),
                    "code": "rate_limit_exceeded",
                    "request_id": request_id,
                    "errors": None,
                },
                headers=headers,
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Scope"] = scope
        return response
