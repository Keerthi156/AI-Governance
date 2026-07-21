"""
Health and readiness endpoints.

Why both:
- /health  → liveness (process alive; used by simple probes)
- /ready   → readiness (DB reachable; used before sending traffic)
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Response, status

from app.core.config import get_settings
from app.core.database import check_database_connection
from app.schemas.health import DatabaseStatus, HealthResponse, ReadyResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Return service liveness metadata (no database dependency)."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={503: {"model": ReadyResponse}},
)
def readiness_check(response: Response) -> ReadyResponse:
    """Return readiness including PostgreSQL connectivity."""
    settings = get_settings()
    db_ok, db_detail = check_database_connection()

    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadyResponse(
        status="ok" if db_ok else "degraded",
        service=settings.app_name,
        environment=settings.app_env,
        timestamp=datetime.now(timezone.utc),
        database=DatabaseStatus(
            status="ok" if db_ok else "error",
            detail=db_detail if db_ok else "database_unreachable",
        ),
    )
