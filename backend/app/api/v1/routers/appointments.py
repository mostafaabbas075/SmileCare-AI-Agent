"""
Appointments router.

Provides endpoints for booking, viewing, rescheduling, cancelling,
and marking appointments as NO_SHOW (enforcing Policy V1 penalty escalation).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Query, Request, status
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

logger = structlog.get_logger(__name__)

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
    request: Request,
    data: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    """Book a new appointment. Validates capacity and Policy V1 limits."""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    appointment = await appointment_service.book_appointment(db, data)

    logger.info(
        "audit_booking_created",
        appointment_id=str(appointment.id),
        patient_id=str(appointment.patient_id),
        ip_address=client_ip,
        user_agent=user_agent,
        action="BOOK_APPOINTMENT",
        timestamp=datetime.now(UTC).isoformat(),
    )

    return AppointmentResponse.model_validate(appointment)


@router.put(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Update / reschedule an appointment",
    description="Update appointment fields. Status transitions and daily edit limits are validated.",
)
async def update_appointment(
    request: Request,
    appointment_id: uuid.UUID,
    data: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    """Apply a partial update to an appointment (reschedule, change status, etc.)."""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    appointment = await appointment_service.update_appointment(db, appointment_id, data)

    logger.info(
        "audit_booking_updated",
        appointment_id=str(appointment_id),
        ip_address=client_ip,
        user_agent=user_agent,
        action="UPDATE_APPOINTMENT",
        timestamp=datetime.now(UTC).isoformat(),
    )

    return AppointmentResponse.model_validate(appointment)


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    summary="Cancel an appointment",
    description="Convenience endpoint to cancel an appointment. Enforces daily cancellation limits and cooldown.",
)
async def cancel_appointment(
    request: Request,
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    """Cancel an active appointment."""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    appointment = await appointment_service.cancel_appointment(db, appointment_id)

    logger.info(
        "audit_booking_cancelled",
        appointment_id=str(appointment_id),
        ip_address=client_ip,
        user_agent=user_agent,
        action="CANCEL_APPOINTMENT",
        timestamp=datetime.now(UTC).isoformat(),
    )

    return AppointmentResponse.model_validate(appointment)


@router.post(
    "/{appointment_id}/no-show",
    response_model=AppointmentResponse,
    summary="Mark appointment as NO_SHOW",
    description="Used by clinic staff when a patient fails to show up. Applies progressive ban penalties (7 days, 30 days, Blacklist).",
)
async def mark_no_show(
    request: Request,
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    """Mark an appointment as NO_SHOW and apply escalation penalties."""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    appointment = await appointment_service.mark_no_show(db, appointment_id)

    logger.info(
        "audit_booking_no_show",
        appointment_id=str(appointment_id),
        ip_address=client_ip,
        user_agent=user_agent,
        action="MARK_NO_SHOW",
        timestamp=datetime.now(UTC).isoformat(),
    )

    return AppointmentResponse.model_validate(appointment)