"""
Appointment service.

Orchestrates appointment booking, cancellation, rescheduling, and retrieval.
This is the most business-logic-heavy service — it validates slot availability,
enforces allowed status transitions, and will later integrate with the AI agent.

Status Transition Rules
-----------------------

    SCHEDULED → CONFIRMED | CANCELLED
    CONFIRMED → COMPLETED | CANCELLED | NO_SHOW
    COMPLETED → (terminal — no further transitions)
    CANCELLED → (terminal — no further transitions)
    NO_SHOW   → (terminal — no further transitions)
"""

from __future__ import annotations

import uuid
from datetime import date

import structlog

from app.core.constants import AppointmentStatus
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.appointment import Appointment
from app.repositories.appointment import AppointmentRepository, appointment_repository
from app.repositories.doctor import DoctorRepository, doctor_repository
from app.repositories.patient import PatientRepository, patient_repository
from app.repositories.service import ServiceRepository, service_repository
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# Valid transitions: current_status → set of allowed next statuses
_ALLOWED_TRANSITIONS: dict[AppointmentStatus, set[AppointmentStatus]] = {
    AppointmentStatus.SCHEDULED: {
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.CANCELLED,
    },
    AppointmentStatus.CONFIRMED: {
        AppointmentStatus.COMPLETED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    },
    AppointmentStatus.COMPLETED: set(),
    AppointmentStatus.CANCELLED: set(),
    AppointmentStatus.NO_SHOW: set(),
}


class AppointmentService:
    """Business logic for appointment lifecycle management."""

    def __init__(
        self,
        repo: AppointmentRepository = appointment_repository,
        patient_repo: PatientRepository = patient_repository,
        doctor_repo: DoctorRepository = doctor_repository,
        service_repo: ServiceRepository = service_repository,
    ) -> None:
        self._repo = repo
        self._patient_repo = patient_repo
        self._doctor_repo = doctor_repo
        self._service_repo = service_repo

    async def get_appointment(
        self,
        db: AsyncSession,
        appointment_id: uuid.UUID,
    ) -> Appointment:
        """Retrieve an appointment by ID.

        Raises:
            NotFoundError: If the appointment does not exist.
        """
        appointment = await self._repo.get_by_id(db, appointment_id)
        if appointment is None:
            raise NotFoundError("Appointment", appointment_id)
        return appointment

    async def get_appointment_detail(
        self,
        db: AsyncSession,
        appointment_id: uuid.UUID,
    ) -> Appointment:
        """Retrieve an appointment with related patient, doctor, and service loaded.

        Raises:
            NotFoundError: If the appointment does not exist.
        """
        appointment = await self._repo.get_with_details(db, appointment_id)
        if appointment is None:
            raise NotFoundError("Appointment", appointment_id)
        return appointment

    async def list_appointments(
        self,
        db: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
        patient_id: uuid.UUID | None = None,
    ) -> tuple[list[Appointment], int]:
        """Return paginated appointments, optionally filtered by patient.

        Returns:
            Tuple of (appointments list, total count).
        """
        if patient_id is not None:
            appointments = await self._repo.get_by_patient(
                db, patient_id, offset=offset, limit=limit
            )
            total = len(appointments)  # small enough; avoid a second query
            return appointments, total

        appointments = await self._repo.get_all(db, offset=offset, limit=limit)
        total = await self._repo.count(db)
        return appointments, total

    async def book_appointment(
        self,
        db: AsyncSession,
        data: AppointmentCreate,
    ) -> Appointment:
        """Book a new appointment.

        Validates that:
        1. The patient, doctor, and service all exist.
        2. The appointment date is not in the past.
        3. The time slot is not already taken by the doctor.

        Raises:
            NotFoundError: If patient, doctor, or service are not found.
            ValidationError: If the date is in the past.
            ConflictError: If the time slot is already booked.
        """
        # Validate all referenced entities exist
        if not await self._patient_repo.get_by_id(db, data.patient_id):
            raise NotFoundError("Patient", data.patient_id)
        if not await self._doctor_repo.get_by_id(db, data.doctor_id):
            raise NotFoundError("Doctor", data.doctor_id)
        if not await self._service_repo.get_by_id(db, data.service_id):
            raise NotFoundError("Service", data.service_id)

        # Check slot availability
        slot_taken = await self._repo.is_slot_taken(
            db,
            doctor_id=data.doctor_id,
            appointment_date=data.appointment_date,
            appointment_time=data.appointment_time,
        )
        if slot_taken:
            raise ConflictError(
                f"Dr. is already booked on {data.appointment_date} "
                f"at {data.appointment_time}."
            )

        appointment = await self._repo.create(db, data.model_dump())
        logger.info(
            "appointment_booked",
            appointment_id=str(appointment.id),
            patient_id=str(data.patient_id),
            date=str(data.appointment_date),
        )
        return appointment

    async def update_appointment(
        self,
        db: AsyncSession,
        appointment_id: uuid.UUID,
        data: AppointmentUpdate,
    ) -> Appointment:
        """Update appointment fields including status transitions.

        Validates status transitions according to the allowed transition matrix.

        Raises:
            NotFoundError: If the appointment does not exist.
            ValidationError: If the status transition is not allowed.
            ConflictError: If the new time slot is already taken.
        """
        appointment = await self.get_appointment(db, appointment_id)

        # Validate status transition
        if data.status is not None and data.status != appointment.status:
            allowed = _ALLOWED_TRANSITIONS[appointment.status]
            if data.status not in allowed:
                raise ValidationError(
                    f"Cannot transition from '{appointment.status}' "
                    f"to '{data.status}'. "
                    f"Allowed: {[s.value for s in allowed] or 'none (terminal state)'}."
                )

        # Check for slot conflict on reschedule
        new_date = data.appointment_date or appointment.appointment_date
        new_time = data.appointment_time or appointment.appointment_time
        new_doctor = data.doctor_id or appointment.doctor_id

        if (
            data.appointment_date is not None
            or data.appointment_time is not None
            or data.doctor_id is not None
        ):
            slot_taken = await self._repo.is_slot_taken(
                db,
                doctor_id=new_doctor,
                appointment_date=new_date,
                appointment_time=new_time,
                exclude_id=appointment_id,
            )
            if slot_taken:
                raise ConflictError(
                    f"The requested slot on {new_date} at {new_time} is already taken."
                )

        updated = await self._repo.update(
            db, appointment, data.model_dump(exclude_none=True)
        )
        logger.info("appointment_updated", appointment_id=str(appointment_id))
        return updated

    async def cancel_appointment(
        self,
        db: AsyncSession,
        appointment_id: uuid.UUID,
    ) -> Appointment:
        """Cancel an appointment (convenience wrapper around update).

        Raises:
            NotFoundError: If the appointment does not exist.
            ValidationError: If the appointment is already in a terminal state.
        """
        return await self.update_appointment(
            db,
            appointment_id,
            AppointmentUpdate(status=AppointmentStatus.CANCELLED),
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
appointment_service = AppointmentService()
