"""
ConversationHistory ORM model.

Persists every message exchanged between a patient and the AI agent,
enabling context recall across sessions and providing an audit trail.

Each row represents one turn (one message from either user or assistant).
The entire conversation thread is identified by a shared ``session_id``.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import MessageRole
from app.database.base_model import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.patient import Patient


class ConversationHistory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single message turn in a patient-AI conversation."""

    __tablename__ = "conversation_history"

    # ------------------------------------------------------------------
    # Foreign Keys
    # ------------------------------------------------------------------
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Linked patient, if identified. NULL for anonymous sessions.",
    )

    # ------------------------------------------------------------------
    # Session tracking
    # ------------------------------------------------------------------
    session_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
        doc="Client-generated session UUID grouping messages into a conversation.",
    )

    # ------------------------------------------------------------------
    # Message content
    # ------------------------------------------------------------------
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, name="message_role_enum"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Raw message text.",
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    patient: Mapped["Patient | None"] = relationship(
        back_populates="conversations",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<ConversationHistory id={self.id} "
            f"session={self.session_id[:8]}... "
            f"role={self.role}>"
        )
