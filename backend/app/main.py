"""
FastAPI application factory and ASGI entrypoint.

Why this file exists:
- Creates the FastAPI app once with middleware, CORS, and routers.
- Keeps startup configuration out of individual route modules.
- `uvicorn app.main:app` loads this module in production and local dev.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.constants import APP_VERSION
from app.core.error_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.services.retention_scheduler import (
    start_retention_scheduler,
    stop_retention_scheduler,
)
from app.services.webhook_retry_worker import (
    start_webhook_retry_worker,
    stop_webhook_retry_worker,
)


@asynccontextmanager
async def lifespan(_application: FastAPI):
    """Start background workers on boot; stop cleanly on shutdown."""
    from app.core.database import SessionLocal
    from app.services.demo_seed_service import seed_demo_accounts

    try:
        db = SessionLocal()
        try:
            seed_demo_accounts(db)
        finally:
            db.close()
    except Exception:  # noqa: BLE001 — demo seed must not block API boot
        logging.getLogger(__name__).exception("Demo account seed skipped")

    start_retention_scheduler()
    start_webhook_retry_worker()
    try:
        yield
    finally:
        stop_webhook_retry_worker()
        stop_retention_scheduler()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    configure_logging()
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        description=(
            "Enterprise AI Governance & Multi-LLM Intelligence Platform API. "
            "Compare models, route prompts, track cost/usage, and enforce policy."
        ),
        version=APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Order matters: last added runs first.
    # Rate limit after request-id logging so 429s still carry X-Request-ID when set.
    application.add_middleware(RateLimitMiddleware)
    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Scope",
            "Retry-After",
        ],
    )

    register_exception_handlers(application)

    application.include_router(api_router, prefix=settings.api_v1_prefix)

    @application.get("/", tags=["root"])
    def root() -> dict[str, str]:
        """Simple root redirect hint for humans hitting the base URL."""
        return {
            "service": settings.app_name,
            "version": APP_VERSION,
            "message": "API is running. See /docs for OpenAPI documentation.",
            "health": f"{settings.api_v1_prefix}/health",
            "meta": f"{settings.api_v1_prefix}/meta",
        }

    return application


app = create_app()
