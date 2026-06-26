"""
Patient repository.

Extends ``BaseRepository`` with patient-specific queries such as
lookup by email or phone (used during AI agent CRM operations).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient
from app.repositories.base import BaseRepository


class PatientRepository(BaseRepository[Patient]):
    """Data access layer for the patients table."""

    model = Patient

    async def get_by_email(
        self,
        db: AsyncSession,
        email: str,
    ) -> Patient | None:
        """Return a patient by email address, or ``None`` if not found.

        Used to detect duplicate registrations and for AI agent patient lookup.
        """
        stmt = select(Patient).where(Patient.email == email.lower())
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_phone(
        self,
        db: AsyncSession,
        phone: str,
    ) -> Patient | None:
        """Return a patient by phone number, or ``None`` if not found."""
        stmt = select(Patient).where(Patient.phone == phone.strip())
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Module-level singleton — injected via FastAPI Depends()
# ---------------------------------------------------------------------------
patient_repository = PatientRepository()
