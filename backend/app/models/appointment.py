"""
Appointment ORM model.

Central entity linking a Patient, Doctor, Service, and Clinic to a specific
date and time. The status field tracks the appointment life-cycle with strict multi-tenant isolation.
"""

from __future__ import annotations

import uuid
from datetime import date, time
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, ForeignKey, String, Text, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import AppointmentStatus
from app.database.base_model import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic
    from app.models.doctor import Doctor
    from app.models.patient import Patient
    from app.models.service import Service


class Appointment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A scheduled appointment between a patient and a doctor for a service within a specific clinic."""

    __tablename__ = "appointments"

    # ------------------------------------------------------------------
    # Foreign Keys
    # ------------------------------------------------------------------
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Multi-clinic tenant identifier.",
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    appointment_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)

    # ------------------------------------------------------------------
    # Status & Notes
    # ------------------------------------------------------------------
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, name="appointment_status_enum"),
        nullable=False,
        default=AppointmentStatus.SCHEDULED,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional free-text notes from the receptionist or patient.",
    )

    # ------------------------------------------------------------------
    # Relationships (Using selectin for Async compatibility)
    # ------------------------------------------------------------------
    clinic: Mapped["Clinic"] = relationship(back_populates="appointments", lazy="selectin")
    patient: Mapped["Patient"] = relationship(back_populates="appointments", lazy="selectin")
    doctor: Mapped["Doctor"] = relationship(back_populates="appointments", lazy="selectin")
    service: Mapped["Service"] = relationship(back_populates="appointments", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<Appointment id={self.id} "
            f"clinic_id={self.clinic_id} "
            f"date={self.appointment_date} "
            f"status={self.status}>"
        )