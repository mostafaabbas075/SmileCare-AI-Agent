"""
Appointment repository.

Extends ``BaseRepository`` with appointment-specific queries needed
by the AI agent's booking, cancellation, and rescheduling tools.
"""

from __future__ import annotations

import uuid
from datetime import date, time

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.constants import AppointmentStatus
from app.models.appointment import Appointment
from app.repositories.base import BaseRepository


class AppointmentRepository(BaseRepository[Appointment]):
    """Data access layer for the appointments table."""

    model = Appointment

    async def get_with_details(
        self,
        db: AsyncSession,
        appointment_id: uuid.UUID,
    ) -> Appointment | None:
        """Return an appointment with patient, doctor, and service eagerly loaded.

        Used in the detail endpoint and AI agent context to avoid N+1 queries.
        """
        stmt = (
            select(Appointment)
            .options(
                joinedload(Appointment.patient),
                joinedload(Appointment.doctor),
                joinedload(Appointment.service),
            )
            .where(Appointment.id == appointment_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_patient(
        self,
        db: AsyncSession,
        patient_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Appointment]:
        """Return paginated appointments for a specific patient."""
        stmt = (
            select(Appointment)
            .where(Appointment.patient_id == patient_id)
            .order_by(Appointment.appointment_date.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_doctor_and_date(
        self,
        db: AsyncSession,
        doctor_id: uuid.UUID,
        appointment_date: date,
    ) -> list[Appointment]:
        """Return all appointments for a doctor on a specific date.

        Used to detect time-slot conflicts when booking.
        """
        stmt = select(Appointment).where(
            and_(
                Appointment.doctor_id == doctor_id,
                Appointment.appointment_date == appointment_date,
                Appointment.status.not_in(  # type: ignore[attr-defined]
                    [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]
                ),
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def is_slot_taken(
        self,
        db: AsyncSession,
        doctor_id: uuid.UUID,
        appointment_date: date,
        appointment_time: time,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        """Return True if the doctor already has an active appointment at this time.

        Args:
            exclude_id: Appointment ID to ignore (used when rescheduling).
        """
        stmt = select(Appointment.id).where(
            and_(
                Appointment.doctor_id == doctor_id,
                Appointment.appointment_date == appointment_date,
                Appointment.appointment_time == appointment_time,
                Appointment.status.not_in(  # type: ignore[attr-defined]
                    [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]
                ),
            )
        )
        if exclude_id is not None:
            stmt = stmt.where(Appointment.id != exclude_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
appointment_repository = AppointmentRepository()
