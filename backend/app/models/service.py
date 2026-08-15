"""
Service ORM model.

Represents a dental treatment or service offered by the clinic,
e.g. "Teeth Whitening", "Root Canal", "Dental Implant".
Includes dynamic toggle (is_active), soft delete support (is_deleted, deleted_at),
and strict multi-tenancy support (clinic_id with Foreign Key).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base_model import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.clinic import Clinic


class Service(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Dental service or treatment offering."""

    __tablename__ = "services"
    __table_args__ = (
        # منع تكرار اسم الخدمة داخل نفس العيادة فقط، والسماح بتكرارها بين عيادات مختلفة
        UniqueConstraint("clinic_id", "name", name="uq_clinic_service_name"),
    )

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Multi-clinic tenant identifier.",
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        doc="Price in the clinic's default currency.",
    )
    duration: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Typical appointment duration in minutes.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether this service is currently available for booking.",
    )

    # ------------------------------------------------------------------
    # Soft Delete Fields
    # ------------------------------------------------------------------
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        doc="Soft delete flag to preserve history and audit logs.",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when the service was soft-deleted.",
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    clinic: Mapped["Clinic"] = relationship(
        back_populates="services",
        lazy="select",
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="service",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<Service id={self.id} clinic_id={self.clinic_id} name='{self.name}' "
            f"price={self.price} is_active={self.is_active} is_deleted={self.is_deleted}>"
        )