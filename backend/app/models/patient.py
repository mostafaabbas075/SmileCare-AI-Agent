"""
Patient ORM model.

Represents a patient registered in the dental clinic system.
Includes multi-tenancy isolation (clinic_id), personal data,
and clinic-specific no-show / blacklist tracking.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import Gender
from app.database.base_model import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.clinic import Clinic
    from app.models.conversation_history import ConversationHistory


class Patient(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Dental clinic patient record with tenant isolation."""

    __tablename__ = "patients"

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Multi-clinic tenant identifier.",
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    gender: Mapped[Gender | None] = mapped_column(
        Enum(Gender, name="gender_enum"), nullable=True
    )
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ------------------------------------------------------------------
    # Blacklist & No-Show Tracking (Clinic-Specific)
    # ------------------------------------------------------------------
    is_blacklisted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    no_show_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default="0"
    )
    banned_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    clinic: Mapped["Clinic"] = relationship(
        back_populates="patients",
        lazy="select",
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="select",
    )
    conversations: Mapped[list["ConversationHistory"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Patient id={self.id} clinic_id={self.clinic_id} name='{self.first_name} {self.last_name}'>"