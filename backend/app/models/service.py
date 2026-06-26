"""
Service ORM model.

Represents a dental treatment or service offered by the clinic,
e.g. "Teeth Whitening", "Root Canal", "Dental Implant".
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base_model import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment


class Service(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Dental service or treatment offering."""

    __tablename__ = "services"

    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
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

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="service",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Service id={self.id} name='{self.name}' price={self.price}>"
