"""
Global exception handlers.

Why this exists:
- Guarantees every error (domain, validation, unexpected) returns the same JSON shape.
- Includes request_id when middleware has set it on the request state.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException
from app.schemas.errors import ErrorResponse

logger = logging.getLogger("app.errors")


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _error_body(
    *,
    detail: str,
    code: str,
    request_id: str | None,
    errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = ErrorResponse(
        detail=detail,
        code=code,
        request_id=request_id,
        errors=errors,
    )
    return payload.model_dump()


def register_exception_handlers(app: FastAPI) -> None:
    """Attach standardized exception handlers to the FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request,
        exc: AppException,
    ) -> JSONResponse:
        request_id = _request_id(request)
        logger.warning(
            "app_error code=%s status=%s detail=%s request_id=%s",
            exc.code,
            exc.status_code,
            exc.message,
            request_id,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(
                detail=exc.message,
                code=exc.code,
                request_id=request_id,
                errors=[exc.details] if exc.details else None,
            ),
            headers={"X-Request-ID": request_id} if request_id else None,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        request_id = _request_id(request)
        field_errors = [
            {
                "loc": [str(part) for part in err.get("loc", ())],
                "msg": err.get("msg"),
                "type": err.get("type"),
            }
            for err in exc.errors()
        ]
        logger.info(
            "validation_error request_id=%s errors=%s",
            request_id,
            field_errors,
        )
        return JSONResponse(
            status_code=422,
            content=_error_body(
                detail="Request validation failed",
                code="validation_error",
                request_id=request_id,
                errors=field_errors,
            ),
            headers={"X-Request-ID": request_id} if request_id else None,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        request_id = _request_id(request)
        detail = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        code = "not_found" if exc.status_code == 404 else "http_error"
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(
                detail=detail,
                code=code,
                request_id=request_id,
            ),
            headers={"X-Request-ID": request_id} if request_id else None,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        request_id = _request_id(request)
        logger.exception(
            "unhandled_error request_id=%s path=%s",
            request_id,
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content=_error_body(
                detail="Internal server error",
                code="internal_error",
                request_id=request_id,
            ),
            headers={"X-Request-ID": request_id} if request_id else None,
        )
