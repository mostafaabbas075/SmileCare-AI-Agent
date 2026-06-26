"""
Doctor Pydantic schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime, time

from pydantic import Field, field_validator

from app.schemas.common import AppBaseModel


class DoctorBase(AppBaseModel):
    """Shared doctor fields."""

    name: str = Field(min_length=1, max_length=200, examples=["Dr. Sarah Mitchell"])
    specialty: str = Field(min_length=1, max_length=150, examples=["Orthodontics"])
    experience_years: int = Field(default=0, ge=0, le=60)
    working_days: str | None = Field(
        default=None,
        max_length=100,
        examples=["Mon,Tue,Wed,Thu,Fri"],
        description="Comma-separated working days.",
    )
    start_time: time | None = Field(default=None, examples=["09:00:00"])
    end_time: time | None = Field(default=None, examples=["17:00:00"])

    @field_validator("working_days")
    @classmethod
    def validate_working_days(cls, v: str | None) -> str | None:
        """Ensure working_days contains only valid day abbreviations."""
        valid_days = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
        if v is None:
            return v
        days = [d.strip() for d in v.split(",")]
        invalid = set(days) - valid_days
        if invalid:
            raise ValueError(
                f"Invalid day(s): {invalid}. "
                f"Use: Mon, Tue, Wed, Thu, Fri, Sat, Sun."
            )
        return ",".join(days)


class DoctorCreate(DoctorBase):
    """Payload for POST /api/v1/doctors."""

    pass


class DoctorUpdate(AppBaseModel):
    """Payload for PUT /api/v1/doctors/{id} — all fields optional."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    specialty: str | None = Field(default=None, min_length=1, max_length=150)
    experience_years: int | None = Field(default=None, ge=0, le=60)
    working_days: str | None = None
    start_time: time | None = None
    end_time: time | None = None


class DoctorResponse(DoctorBase):
    """Doctor representation returned by API responses."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
