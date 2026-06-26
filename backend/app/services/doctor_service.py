"""
Doctor service.

Orchestrates doctor management operations, enforcing business rules
such as validating that end_time is after start_time.
"""

from __future__ import annotations

import uuid

import structlog

from app.core.exceptions import NotFoundError, ValidationError
from app.models.doctor import Doctor
from app.repositories.doctor import DoctorRepository, doctor_repository
from app.schemas.doctor import DoctorCreate, DoctorUpdate
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class DoctorService:
    """Business logic for doctor management."""

    def __init__(self, repo: DoctorRepository = doctor_repository) -> None:
        self._repo = repo

    async def get_doctor(
        self,
        db: AsyncSession,
        doctor_id: uuid.UUID,
    ) -> Doctor:
        """Retrieve a doctor by ID.

        Raises:
            NotFoundError: If the doctor does not exist.
        """
        doctor = await self._repo.get_by_id(db, doctor_id)
        if doctor is None:
            raise NotFoundError("Doctor", doctor_id)
        return doctor

    async def list_doctors(
        self,
        db: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
        specialty: str | None = None,
    ) -> tuple[list[Doctor], int]:
        """Return a paginated, optionally filtered list of doctors.

        Returns:
            Tuple of (doctors list, total count).
        """
        if specialty:
            doctors = await self._repo.get_by_specialty(db, specialty)
            return doctors, len(doctors)

        doctors = await self._repo.get_all(db, offset=offset, limit=limit)
        total = await self._repo.count(db)
        return doctors, total

    async def create_doctor(
        self,
        db: AsyncSession,
        data: DoctorCreate,
    ) -> Doctor:
        """Create a new doctor record.

        Raises:
            ValidationError: If end_time is not after start_time.
        """
        self._validate_schedule(data.start_time, data.end_time)
        doctor = await self._repo.create(db, data.model_dump())
        logger.info("doctor_created", doctor_id=str(doctor.id), name=doctor.name)
        return doctor

    async def update_doctor(
        self,
        db: AsyncSession,
        doctor_id: uuid.UUID,
        data: DoctorUpdate,
    ) -> Doctor:
        """Apply a partial update to a doctor record.

        Raises:
            NotFoundError: If the doctor does not exist.
            ValidationError: If schedule times are inconsistent.
        """
        doctor = await self.get_doctor(db, doctor_id)
        start = data.start_time or doctor.start_time
        end = data.end_time or doctor.end_time
        self._validate_schedule(start, end)

        updated = await self._repo.update(db, doctor, data.model_dump(exclude_none=True))
        logger.info("doctor_updated", doctor_id=str(doctor_id))
        return updated

    async def delete_doctor(
        self,
        db: AsyncSession,
        doctor_id: uuid.UUID,
    ) -> None:
        """Delete a doctor record.

        Raises:
            NotFoundError: If the doctor does not exist.
        """
        doctor = await self.get_doctor(db, doctor_id)
        await self._repo.delete(db, doctor)
        logger.info("doctor_deleted", doctor_id=str(doctor_id))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_schedule(start_time: object, end_time: object) -> None:
        """Ensure end_time is strictly after start_time when both are provided."""
        if start_time is not None and end_time is not None:
            if end_time <= start_time:  # type: ignore[operator]
                raise ValidationError("end_time must be later than start_time.")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
doctor_service = DoctorService()
