"""
Service Pydantic schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.common import AppBaseModel


class ServiceBase(AppBaseModel):
    """Shared service fields."""

    name: str = Field(min_length=1, max_length=200, examples=["Teeth Whitening"])
    description: str | None = Field(
        default=None, examples=["Professional in-clinic teeth whitening treatment."]
    )
    price: Decimal = Field(
        gt=0,
        decimal_places=2,
        examples=["150.00"],
        description="Service price. Must be positive.",
    )
    duration: int = Field(
        gt=0,
        le=480,
        examples=[60],
        description="Appointment duration in minutes (max 8 hours).",
    )


class ServiceCreate(ServiceBase):
    """Payload for POST /api/v1/services."""

    pass


class ServiceUpdate(AppBaseModel):
    """Payload for PUT /api/v1/services/{id} — all fields optional."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    price: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    duration: int | None = Field(default=None, gt=0, le=480)


class ServiceResponse(ServiceBase):
    """Service representation returned by API responses."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
