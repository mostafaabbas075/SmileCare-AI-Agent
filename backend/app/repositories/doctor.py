"""
Doctor repository.

Extends ``BaseRepository`` with doctor-specific queries such as
filtering by specialty and checking availability by working day.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doctor import Doctor
from app.repositories.base import BaseRepository


class DoctorRepository(BaseRepository[Doctor]):
    """Data access layer for the doctors table."""

    model = Doctor

    async def get_by_specialty(
        self,
        db: AsyncSession,
        specialty: str,
    ) -> list[Doctor]:
        """Return all doctors matching the given specialty.

        Case-insensitive match so 'orthodontics' and 'Orthodontics' both work.
        """
        stmt = select(Doctor).where(
            Doctor.specialty.ilike(f"%{specialty}%")
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_available_on_day(
        self,
        db: AsyncSession,
        day_abbr: str,
    ) -> list[Doctor]:
        """Return doctors who work on the given day abbreviation.

        Args:
            day_abbr: Three-letter day abbreviation, e.g. 'Mon', 'Tue'.
        """
        stmt = select(Doctor).where(
            Doctor.working_days.ilike(f"%{day_abbr}%")  # type: ignore[union-attr]
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
doctor_repository = DoctorRepository()
