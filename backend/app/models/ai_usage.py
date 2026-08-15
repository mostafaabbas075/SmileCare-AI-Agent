"""
AI Usage & Token Tracking Model per Clinic.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base_model import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic


class AIUsageLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_usage_logs"

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    message_length: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    response_length: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    estimated_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    cost_usd: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    clinic: Mapped["Clinic"] = relationship(
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<AIUsageLog id={self.id} clinic_id={self.clinic_id} tokens={self.estimated_tokens}>"