"""
Common / shared Pydantic schemas.

Provides:

- ``PaginatedResponse[T]`` — generic paginated list wrapper
- ``MessageResponse`` — simple success/info message
- ``ErrorResponse`` — standard error envelope
- ``IDResponse`` — returns only the created/updated resource's ID
"""

from __future__ import annotations

import uuid
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class AppBaseModel(BaseModel):
    """Base for all application schemas.

    Enables ``from_attributes`` (formerly ``orm_mode``) so schemas can be
    built directly from SQLAlchemy model instances.
    """

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class PaginationParams(AppBaseModel):
    """Query parameters for paginated list endpoints."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed).")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page.")

    @property
    def offset(self) -> int:
        """SQL OFFSET for the current page."""
        return (self.page - 1) * self.page_size


class PaginatedResponse(AppBaseModel, Generic[T]):
    """Generic paginated response envelope.

    Usage::

        return PaginatedResponse[PatientResponse](
            data=patients,
            total=total_count,
            page=params.page,
            page_size=params.page_size,
        )
    """

    data: list[T]
    total: int = Field(description="Total number of records matching the query.")
    page: int = Field(description="Current page number.")
    page_size: int = Field(description="Number of items per page.")
    total_pages: int = Field(description="Total number of pages.")

    @classmethod
    def create(
        cls,
        data: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse[T]":
        """Factory method to avoid computing total_pages at every call site."""
        import math

        return cls(
            data=data,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if page_size > 0 else 0,
        )


# ---------------------------------------------------------------------------
# Standard response wrappers
# ---------------------------------------------------------------------------

class MessageResponse(AppBaseModel):
    """Simple success / informational message."""

    message: str


class IDResponse(AppBaseModel):
    """Returns the UUID of the created or affected resource."""

    id: uuid.UUID


class ErrorResponse(AppBaseModel):
    """Standard error envelope returned by the global exception handler."""

    error: str = Field(description="Machine-readable error type / code.")
    message: str = Field(description="Human-readable error description.")
    detail: object | None = Field(
        default=None,
        description="Optional structured details (validation errors, etc.).",
    )
