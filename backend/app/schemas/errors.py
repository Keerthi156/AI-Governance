"""Standard API error response schema."""

from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """
    Consistent error envelope returned by all exception handlers.

    Example:
    {
      "detail": "Request validation failed",
      "code": "validation_error",
      "request_id": "…",
      "errors": [{"loc": ["body", "prompt"], "msg": "Field required", ...}]
    }
    """

    detail: str = Field(..., description="Human-readable error summary")
    code: str = Field(..., description="Machine-stable error code")
    request_id: str | None = Field(
        default=None,
        description="Correlation ID from X-Request-ID / middleware",
    )
    errors: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional structured field or domain error details",
    )
