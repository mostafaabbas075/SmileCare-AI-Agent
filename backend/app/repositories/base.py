"""
Generic async CRUD base repository.

All entity repositories inherit from ``BaseRepository[T]`` and get standard
CRUD operations for free. Entity-specific queries are added in subclasses.

Design decisions:

- ``AsyncSession`` is passed in per-call (not stored on the instance) so
  the repository remains stateless and testable without mocks.
- All public methods are typed with the model class ``T`` so callers get
  full IDE auto-complete.
- Count queries use ``func.count()`` to avoid fetching rows just for pagination.
"""

from __future__ import annotations

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base_model import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic async CRUD repository.

    Usage::

        class PatientRepository(BaseRepository[Patient]):
            model = Patient
    """

    model: type[ModelT]

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_id(
        self,
        db: AsyncSession,
        record_id: uuid.UUID,
    ) -> ModelT | None:
        """Return a single record by primary key, or ``None`` if not found."""
        result = await db.get(self.model, record_id)
        return result

    async def get_all(
        self,
        db: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[ModelT]:
        """Return a paginated list of records.

        Args:
            db: Active async database session.
            offset: Number of records to skip.
            limit: Maximum number of records to return.
            filters: Optional equality filters as ``{column_name: value}``.
        """
        stmt = select(self.model)
        if filters:
            for column, value in filters.items():
                stmt = stmt.where(getattr(self.model, column) == value)
        stmt = stmt.offset(offset).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count(
        self,
        db: AsyncSession,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """Return total record count matching optional filters."""
        stmt = select(func.count()).select_from(self.model)
        if filters:
            for column, value in filters.items():
                stmt = stmt.where(getattr(self.model, column) == value)
        result = await db.execute(stmt)
        return result.scalar_one()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def create(
        self,
        db: AsyncSession,
        data: dict[str, Any],
    ) -> ModelT:
        """Insert a new record and return it with its generated ID.

        Args:
            db: Active async database session.
            data: Dictionary of column-value pairs (from schema.model_dump()).
        """
        instance = self.model(**data)
        db.add(instance)
        await db.flush()      # flush to get DB-generated defaults (id, timestamps)
        await db.refresh(instance)
        return instance

    async def update(
        self,
        db: AsyncSession,
        instance: ModelT,
        data: dict[str, Any],
    ) -> ModelT:
        """Apply a partial update to an existing record.

        Args:
            db: Active async database session.
            instance: The ORM instance to update.
            data: Dictionary of fields to change (None values are skipped).
        """
        for field, value in data.items():
            if value is not None:
                setattr(instance, field, value)
        db.add(instance)
        await db.flush()
        await db.refresh(instance)
        return instance

    async def delete(
        self,
        db: AsyncSession,
        instance: ModelT,
    ) -> None:
        """Delete a record from the database.

        Args:
            db: Active async database session.
            instance: The ORM instance to delete.
        """
        await db.delete(instance)
        await db.flush()
