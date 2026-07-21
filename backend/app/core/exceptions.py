"""
Application-level exceptions and HTTP error contracts.

Why this exists:
- Routes raise domain exceptions instead of crafting Response objects.
- Handlers convert them into a single JSON error shape for the frontend.
"""

from typing import Any


class AppException(Exception):
    """Base exception for expected, client-facing API errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "app_error",
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppException):
    """Resource was not found."""

    def __init__(self, message: str = "Resource not found", **kwargs: Any) -> None:
        super().__init__(message, code="not_found", status_code=404, **kwargs)


class ValidationAppError(AppException):
    """Domain validation failed (distinct from FastAPI request validation)."""

    def __init__(self, message: str = "Validation failed", **kwargs: Any) -> None:
        super().__init__(message, code="validation_error", status_code=422, **kwargs)


class UnauthorizedError(AppException):
    """Caller is not authenticated or credentials are invalid."""

    def __init__(self, message: str = "Unauthorized", **kwargs: Any) -> None:
        super().__init__(message, code="unauthorized", status_code=401, **kwargs)


class ForbiddenError(AppException):
    """Caller is authenticated but not allowed to perform the action."""

    def __init__(self, message: str = "Forbidden", **kwargs: Any) -> None:
        super().__init__(message, code="forbidden", status_code=403, **kwargs)


class PolicyViolationError(AppException):
    """Request blocked by an active governance policy."""

    def __init__(self, message: str = "Policy violation", **kwargs: Any) -> None:
        kwargs.setdefault("code", "policy_violation")
        kwargs.setdefault("status_code", 403)
        super().__init__(message, **kwargs)


class ConflictError(AppException):
    """Resource conflict (e.g. duplicate email)."""

    def __init__(self, message: str = "Conflict", **kwargs: Any) -> None:
        super().__init__(message, code="conflict", status_code=409, **kwargs)
