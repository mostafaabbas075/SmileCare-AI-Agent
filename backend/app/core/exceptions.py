"""
Custom exception hierarchy.

All application-specific exceptions derive from ``AppException``. This
enables a single exception handler in ``main.py`` to catch them all and
return consistent HTTP responses.

Hierarchy::

    AppException
    ├── NotFoundError          → 404
    ├── ConflictError          → 409
    ├── ValidationError        → 422
    ├── PermissionDeniedError  → 403
    ├── UnauthorizedError      → 401
    └── ServiceUnavailableError → 503

Usage::

    raise NotFoundError("Patient", patient_id)
"""

from __future__ import annotations

from typing import Any


class AppException(Exception):
    """Base exception for all application-specific errors.

    Args:
        message: Human-readable error description.
        status_code: HTTP status code to return.
        detail: Optional structured detail (serialised to JSON response).
    """

    status_code: int = 500
    default_message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        detail: Any = None,
    ) -> None:
        self.message = message or self.default_message
        self.detail = detail
        super().__init__(self.message)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r})"


# ---------------------------------------------------------------------------
# 404 Not Found
# ---------------------------------------------------------------------------
class NotFoundError(AppException):
    """Raised when a requested resource does not exist in the database."""

    status_code = 404
    default_message = "Resource not found."

    def __init__(self, resource: str, identifier: Any = None) -> None:
        if identifier is not None:
            message = f"{resource} with identifier '{identifier}' was not found."
        else:
            message = f"{resource} was not found."
        super().__init__(message=message)


# ---------------------------------------------------------------------------
# 409 Conflict
# ---------------------------------------------------------------------------
class ConflictError(AppException):
    """Raised when an operation violates a uniqueness or state constraint.

    Examples: duplicate email, double-booking a time slot.
    """

    status_code = 409
    default_message = "A conflict occurred with the current state of the resource."


# ---------------------------------------------------------------------------
# 422 Unprocessable Entity
# ---------------------------------------------------------------------------
class ValidationError(AppException):
    """Raised for domain-level validation failures (beyond Pydantic parsing).

    Use this for business rule violations, e.g. booking in the past.
    """

    status_code = 422
    default_message = "The provided data is invalid."


# ---------------------------------------------------------------------------
# 403 Forbidden
# ---------------------------------------------------------------------------
class PermissionDeniedError(AppException):
    """Raised when an authenticated user lacks the required role/permission."""

    status_code = 403
    default_message = "You do not have permission to perform this action."


# ---------------------------------------------------------------------------
# 401 Unauthorized
# ---------------------------------------------------------------------------
class UnauthorizedError(AppException):
    """Raised when authentication credentials are missing or invalid."""

    status_code = 401
    default_message = "Authentication is required to access this resource."


# ---------------------------------------------------------------------------
# 503 Service Unavailable
# ---------------------------------------------------------------------------
class ServiceUnavailableError(AppException):
    """Raised when a downstream service (LLM, Qdrant, etc.) is unreachable."""

    status_code = 503
    default_message = "A required service is temporarily unavailable."
