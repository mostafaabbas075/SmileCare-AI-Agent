"""
Service repository.

Extends ``BaseRepository`` with dental-service-specific queries.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.repositories.base import BaseRepository


class ServiceRepository(BaseRepository[Service]):
    """Data access layer for the services table."""

    model = Service

    async def get_by_name(
        self,
        db: AsyncSession,
        name: str,
    ) -> Service | None:
        """Return a service by exact name, or ``None`` if not found.

        Used when creating services to enforce the unique name constraint
        at the application level before hitting the DB constraint.
        """
        stmt = select(Service).where(Service.name == name.strip())
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def search_by_name(
        self,
        db: AsyncSession,
        query: str,
    ) -> list[Service]:
        """Return services whose name contains the query string (case-insensitive)."""
        stmt = select(Service).where(Service.name.ilike(f"%{query}%"))
        result = await db.execute(stmt)
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
service_repository = ServiceRepository()
