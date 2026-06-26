"""
Doctors router.

Provides full CRUD endpoints for doctor management, plus filtering
by specialty via an optional query parameter.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.doctor import DoctorCreate, DoctorResponse, DoctorUpdate
from app.services.doctor_service import doctor_service
from app.utils.pagination import PaginationDep

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get(
    "",
    response_model=PaginatedResponse[DoctorResponse],
    summary="List all doctors",
    description="Returns a paginated list of doctors. Filter by specialty using the `specialty` query parameter.",
)
async def list_doctors(
    pagination: PaginationDep,
    specialty: str | None = Query(
        default=None,
        description="Filter doctors by specialty (case-insensitive, partial match).",
    ),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[DoctorResponse]:
    """Return a paginated, optionally filtered list of doctors."""
    doctors, total = await doctor_service.list_doctors(
        db,
        offset=pagination.offset,
        limit=pagination.page_size,
        specialty=specialty,
    )
    return PaginatedResponse.create(
        data=[DoctorResponse.model_validate(d) for d in doctors],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/{doctor_id}",
    response_model=DoctorResponse,
    summary="Get doctor by ID",
)
async def get_doctor(
    doctor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DoctorResponse:
    """Return a single doctor by UUID."""
    doctor = await doctor_service.get_doctor(db, doctor_id)
    return DoctorResponse.model_validate(doctor)


@router.post(
    "",
    response_model=DoctorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new doctor",
)
async def create_doctor(
    data: DoctorCreate,
    db: AsyncSession = Depends(get_db),
) -> DoctorResponse:
    """Create a new doctor record."""
    doctor = await doctor_service.create_doctor(db, data)
    return DoctorResponse.model_validate(doctor)


@router.put(
    "/{doctor_id}",
    response_model=DoctorResponse,
    summary="Update doctor information",
)
async def update_doctor(
    doctor_id: uuid.UUID,
    data: DoctorUpdate,
    db: AsyncSession = Depends(get_db),
) -> DoctorResponse:
    """Apply a partial update to a doctor record."""
    doctor = await doctor_service.update_doctor(db, doctor_id, data)
    return DoctorResponse.model_validate(doctor)


@router.delete(
    "/{doctor_id}",
    response_model=MessageResponse,
    summary="Remove a doctor",
)
async def delete_doctor(
    doctor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Delete a doctor record."""
    await doctor_service.delete_doctor(db, doctor_id)
    return MessageResponse(message=f"Doctor {doctor_id} deleted successfully.")
