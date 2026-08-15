"""
Clinic ORM model for Multi-Tenancy.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any
from sqlalchemy import Boolean, JSON, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base_model import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.doctor import Doctor
    from app.models.patient import Patient
    from app.models.service import Service
    from app.models.user import User


class Clinic(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Dental clinic tenant record."""

    __tablename__ = "clinics"

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    branding: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=False,
        default=dict,
        server_default="{}",
    )
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=False,
        default=dict,
        server_default="{}",
    )

    # ── Relationships ────────────────────────────────────────────────────────
    users: Mapped[list["User"]] = relationship(
        back_populates="clinic",
        cascade="all, delete-orphan",
        lazy="select",
    )
    doctors: Mapped[list["Doctor"]] = relationship(
        back_populates="clinic",
        cascade="all, delete-orphan",
        lazy="select",
    )
    services: Mapped[list["Service"]] = relationship(
        back_populates="clinic",
        cascade="all, delete-orphan",
        lazy="select",
    )
    patients: Mapped[list["Patient"]] = relationship(
        back_populates="clinic",
        cascade="all, delete-orphan",
        lazy="select",
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="clinic",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Clinic id={self.id} slug='{self.slug}' name='{self.name}'>"