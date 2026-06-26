"""
Pagination utilities.

Provides ``PaginationParams`` as a FastAPI-injectable dependency so
pagination query parameters are consistently handled across all list endpoints.

Usage in a router::

    @router.get("/patients")
    async def list_patients(
        pagination: PaginationDep,
        db: AsyncSession = Depends(get_db),
    ) -> PaginatedResponse[PatientResponse]:
        patients, total = await patient_service.list_patients(
            db,
            offset=pagination.offset,
            limit=pagination.page_size,
        )
        return PaginatedResponse.create(
            data=patients,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query

from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


class PaginationParams:
    """Dependency-injectable pagination query parameters.

    Injects ``page`` and ``page_size`` from the query string with
    sensible defaults and upper bounds.
    """

    def __init__(
        self,
        page: int = Query(default=1, ge=1, description="Page number (1-indexed)."),
        page_size: int = Query(
            default=DEFAULT_PAGE_SIZE,
            ge=1,
            le=MAX_PAGE_SIZE,
            description=f"Items per page (max {MAX_PAGE_SIZE}).",
        ),
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        """SQL OFFSET computed from page and page_size."""
        return (self.page - 1) * self.page_size


# Annotated type alias — used as the dependency type in router function signatures.
# Cleaner than writing ``Depends(PaginationParams)`` on every endpoint.
PaginationDep = Annotated[PaginationParams, Depends(PaginationParams)]
