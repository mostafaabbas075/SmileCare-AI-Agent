"""
Appointment Pydantic schemas.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from pydantic import Field, field_validator

from app.core.constants import AppointmentStatus
from app.schemas.common import AppBaseModel
from app.schemas.doctor import DoctorResponse
from app.schemas.patient import PatientResponse
from app.schemas.service import ServiceResponse


class AppointmentBase(AppBaseModel):
    """Shared appointment fields."""

    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    service_id: uuid.UUID
    appointment_date: date = Field(description="Date of the appointment (YYYY-MM-DD).")
    appointment_time: time = Field(description="Start time of the appointment (HH:MM:SS).")
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("appointment_date")
    @classmethod
    def date_not_in_past(cls, v: date) -> date:
        """Prevent booking appointments in the past."""
        if v < date.today():
            raise ValueError("Appointment date cannot be in the past.")
        return v


class AppointmentCreate(AppointmentBase):
    """Payload for POST /api/v1/appointments."""

    pass


class AppointmentUpdate(AppBaseModel):
    """Payload for PUT /api/v1/appointments/{id} — all fields optional."""

    doctor_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    appointment_date: date | None = None
    appointment_time: time | None = None
    status: AppointmentStatus | None = None
    notes: str | None = Field(default=None, max_length=2000)


class AppointmentResponse(AppBaseModel):
    """Appointment returned by API responses (flat, IDs only)."""

    id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    service_id: uuid.UUID
    appointment_date: date
    appointment_time: time
    status: AppointmentStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime


class AppointmentDetailResponse(AppBaseModel):
    """Appointment with nested patient, doctor, and service objects."""

    id: uuid.UUID
    patient: PatientResponse
    doctor: DoctorResponse
    service: ServiceResponse
    appointment_date: date
    appointment_time: time
    status: AppointmentStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime
