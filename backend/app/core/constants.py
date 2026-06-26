"""
Shared enumerations and string constants.

All domain-specific enums live here to avoid circular imports and to provide
a single place to update values used across models, schemas, and business logic.
"""

from __future__ import annotations

from enum import StrEnum


class AppointmentStatus(StrEnum):
    """Life-cycle states of an appointment."""

    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class Gender(StrEnum):
    """Patient biological gender options."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class UserRole(StrEnum):
    """Authentication roles (used when auth is implemented)."""

    ADMIN = "admin"
    RECEPTIONIST = "receptionist"


class MessageRole(StrEnum):
    """Speaker role in a conversation history entry."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class DocumentStatus(StrEnum):
    """Processing state of a knowledge base document."""

    PENDING = "pending"        # uploaded, not yet embedded
    PROCESSING = "processing"  # embedding in progress
    INDEXED = "indexed"        # available in vector store
    FAILED = "failed"          # embedding failed


# ---------------------------------------------------------------------------
# String Constants
# ---------------------------------------------------------------------------
DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100
API_V1_PREFIX: str = "/api/v1"
HEALTH_CHECK_PATH: str = "/health"
