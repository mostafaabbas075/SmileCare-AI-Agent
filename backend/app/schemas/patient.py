"""
Patient Pydantic schemas.

Follows the Base → Create → Update → Response pattern:

- ``PatientBase``   — shared fields with validation rules
- ``PatientCreate`` — fields required when creating a patient
- ``PatientUpdate`` — all fields optional for PATCH semantics
- ``PatientResponse`` — fields returned in API responses (includes id, timestamps)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import EmailStr, Field, field_validator

from app.core.constants import Gender
from app.schemas.common import AppBaseModel


class PatientBase(AppBaseModel):
    """Shared patient fields with validation rules."""

    first_name: str = Field(min_length=1, max_length=100, examples=["John"])
    last_name: str = Field(min_length=1, max_length=100, examples=["Doe"])
    gender: Gender | None = Field(default=None)
    birth_date: date | None = Field(default=None)
    phone: str | None = Field(default=None, max_length=20, examples=["+1-555-0100"])
    email: EmailStr | None = Field(default=None, examples=["john.doe@email.com"])
    city: str | None = Field(default=None, max_length=100, examples=["New York"])

    @field_validator("birth_date")
    @classmethod
    def birth_date_not_future(cls, v: date | None) -> date | None:
        """Ensure birth date is not in the future."""
        if v is not None and v > date.today():
            raise ValueError("Birth date cannot be in the future.")
        return v

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v: str | None) -> str | None:
        """Strip whitespace from phone numbers."""
        return v.strip() if v else v


class PatientCreate(PatientBase):
    """Payload for POST /api/v1/patients."""

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class PatientUpdate(AppBaseModel):
    """Payload for PUT /api/v1/patients/{id} — all fields optional."""

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    gender: Gender | None = None
    birth_date: date | None = None
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    city: str | None = Field(default=None, max_length=100)


class PatientResponse(PatientBase):
    """Patient representation returned by API responses."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
