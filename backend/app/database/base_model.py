"""
Declarative base and shared model mixin.

All ORM models inherit from ``Base``. The ``TimestampMixin`` adds
``created_at`` and ``updated_at`` columns automatically via
``onupdate=func.now()``.

Every table uses a UUID primary key stored as a native PostgreSQL UUID type,
avoiding the integer auto-increment pattern that leaks row count information.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models.

    Inheriting from this class registers the model with SQLAlchemy's
    metadata, which Alembic uses for ``--autogenerate``.
    """

    pass


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` audit columns to any model.

    Usage::

        class Patient(Base, TimestampMixin):
            ...
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        doc="Timestamp when the record was created (set by the database).",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Timestamp of the most recent update (auto-updated by the database).",
    )


class UUIDPrimaryKeyMixin:
    """Adds a UUID primary key column.

    Uses PostgreSQL's native UUID type for efficient storage and indexing.
    The default is generated in Python (not the DB) so we know the ID
    before the INSERT completes — useful for logging and response bodies.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique record identifier (UUID v4).",
    )
