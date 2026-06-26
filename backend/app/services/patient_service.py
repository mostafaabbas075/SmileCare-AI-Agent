"""
Patient service.

Orchestrates repository calls and enforces business rules for patient
management. This layer is the only place that should contain business
logic — routers call services, services call repositories.

Design decisions:

- All methods are async to match the async repository layer.
- The ``AsyncSession`` is passed in from the router via DI, so the service
  has no knowledge of the session lifecycle (commit/rollback happens in the
  dependency).
- ``NotFoundError`` and ``ConflictError`` are raised here, not in the router,
  keeping HTTP concerns out of the business layer.
"""

from __future__ import annotations

import uuid

import structlog

from app.core.exceptions import ConflictError, NotFoundError
from app.models.patient import Patient
from app.repositories.patient import PatientRepository, patient_repository
from app.schemas.patient import PatientCreate, PatientUpdate
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class PatientService:
    """Business logic for patient management."""

    def __init__(self, repo: PatientRepository = patient_repository) -> None:
        self._repo = repo

    async def get_patient(
        self,
        db: AsyncSession,
        patient_id: uuid.UUID,
    ) -> Patient:
        """Retrieve a patient by ID.

        Raises:
            NotFoundError: If the patient does not exist.
        """
        patient = await self._repo.get_by_id(db, patient_id)
        if patient is None:
            raise NotFoundError("Patient", patient_id)
        return patient

    async def list_patients(
        self,
        db: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Patient], int]:
        """Return a paginated list of patients and total count.

        Returns:
            Tuple of (patients list, total count).
        """
        patients = await self._repo.get_all(db, offset=offset, limit=limit)
        total = await self._repo.count(db)
        return patients, total

    async def create_patient(
        self,
        db: AsyncSession,
        data: PatientCreate,
    ) -> Patient:
        """Create a new patient record.

        Raises:
            ConflictError: If a patient with the same email already exists.
        """
        if data.email:
            existing = await self._repo.get_by_email(db, data.email)
            if existing is not None:
                raise ConflictError(
                    f"A patient with email '{data.email}' already exists."
                )

        patient = await self._repo.create(
            db, data.model_dump(exclude_none=False)
        )
        logger.info("patient_created", patient_id=str(patient.id))
        return patient

    async def update_patient(
        self,
        db: AsyncSession,
        patient_id: uuid.UUID,
        data: PatientUpdate,
    ) -> Patient:
        """Apply a partial update to an existing patient.

        Raises:
            NotFoundError: If the patient does not exist.
            ConflictError: If the new email is already taken.
        """
        patient = await self.get_patient(db, patient_id)

        if data.email and data.email != patient.email:
            existing = await self._repo.get_by_email(db, data.email)
            if existing is not None:
                raise ConflictError(
                    f"A patient with email '{data.email}' already exists."
                )

        updated = await self._repo.update(
            db, patient, data.model_dump(exclude_none=True)
        )
        logger.info("patient_updated", patient_id=str(patient_id))
        return updated

    async def delete_patient(
        self,
        db: AsyncSession,
        patient_id: uuid.UUID,
    ) -> None:
        """Delete a patient record.

        Raises:
            NotFoundError: If the patient does not exist.
        """
        patient = await self.get_patient(db, patient_id)
        await self._repo.delete(db, patient)
        logger.info("patient_deleted", patient_id=str(patient_id))


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
patient_service = PatientService()
