"""
Doctor ORM model.

Represents a dental professional working at the clinic.
Working hours are stored as Time columns; working_days is stored as a
comma-separated string. Includes multi-tenant isolation via clinic_id.
"""

from __future__ import annotations

import uuid
from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base_model import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.clinic import Clinic


class Doctor(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Dental clinic doctor / specialist with tenant isolation."""

    __tablename__ = "doctors"

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Multi-clinic tenant identifier.",
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    specialty: Mapped[str] = mapped_column(String(150), nullable=False)
    experience_years: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Working schedule
    working_days: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Comma-separated working days. E.g. 'Mon,Tue,Wed,Thu,Fri'.",
    )
    start_time: Mapped[time | None] = mapped_column(
        Time(timezone=False),
        nullable=True,
        doc="Daily start time (clinic local time).",
    )
    end_time: Mapped[time | None] = mapped_column(
        Time(timezone=False),
        nullable=True,
        doc="Daily end time (clinic local time).",
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    clinic: Mapped["Clinic"] = relationship(
        back_populates="doctors",
        lazy="select",
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="doctor",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Doctor id={self.id} clinic_id={self.clinic_id} name='{self.name}' specialty='{self.specialty}'>"