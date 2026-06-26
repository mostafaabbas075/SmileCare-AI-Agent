"""
Appointments router.

Provides endpoints for booking, viewing, rescheduling, and cancelling
appointments. Includes both a flat response and a detailed (nested) response.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentDetailResponse,
    AppointmentResponse,
    AppointmentUpdate,
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.appointment_service import appointment_service
from app.utils.pagination import PaginationDep

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.get(
    "",
    response_model=PaginatedResponse[AppointmentResponse],
    summary="List appointments",
    description="Returns a paginated list of appointments. Filter by patient_id to list a specific patient's appointments.",
)
async def list_appointments(
    pagination: PaginationDep,
    patient_id: uuid.UUID | None = Query(
        default=None,
        description="Filter appointments by patient UUID.",
    ),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AppointmentResponse]:
    """Return a paginated list of appointments."""
    appointments, total = await appointment_service.list_appointments(
        db,
        offset=pagination.offset,
        limit=pagination.page_size,
        patient_id=patient_id,
    )
    return PaginatedResponse.create(
        data=[AppointmentResponse.model_validate(a) for a in appointments],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/{appointment_id}",
    response_model=AppointmentDetailResponse,
    summary="Get appointment with full details",
    description="Returns an appointment with nested patient, doctor, and service objects.",
)
async def get_appointment(
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AppointmentDetailResponse:
    """Return a single appointment with all related data eagerly loaded."""
    appointment = await appointment_service.get_appointment_detail(db, appointment_id)
    return AppointmentDetailResponse.model_validate(appointment)


@router.post(
    "",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book a new appointment",
)
async def book_appointment(
    data: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    """Book a new appointment. Validates slot availability before creating."""
    appointment = await appointment_service.book_appointment(db, data)
    return AppointmentResponse.model_validate(appointment)


@router.put(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Update / reschedule an appointment",
    description="Update appointment fields. Status transitions are validated against allowed life-cycle rules.",
)
async def update_appointment(
    appointment_id: uuid.UUID,
    data: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    """Apply a partial update to an appointment (reschedule, change status, etc.)."""
    appointment = await appointment_service.update_appointment(db, appointment_id, data)
    return AppointmentResponse.model_validate(appointment)


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    summary="Cancel an appointment",
    description="Convenience endpoint to cancel an appointment without needing to send the full update payload.",
)
async def cancel_appointment(
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    """Cancel an active appointment."""
    appointment = await appointment_service.cancel_appointment(db, appointment_id)
    return AppointmentResponse.model_validate(appointment)
