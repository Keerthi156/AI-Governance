"""Health / readiness response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness payload — process is up (does not require DB)."""

    status: str = Field(..., examples=["ok"])
    service: str = Field(..., examples=["AI_GOVERNANCE"])
    environment: str = Field(..., examples=["development"])
    timestamp: datetime


class DatabaseStatus(BaseModel):
    """Database subsystem status."""

    status: str = Field(..., examples=["ok", "error"])
    detail: str = Field(..., examples=["connected"])


class ReadyResponse(BaseModel):
    """
    Readiness payload — safe for load balancers to route traffic.

    Returns HTTP 503 when the database is unreachable.
    """

    status: str = Field(..., examples=["ok", "degraded"])
    service: str
    environment: str
    timestamp: datetime
    database: DatabaseStatus
