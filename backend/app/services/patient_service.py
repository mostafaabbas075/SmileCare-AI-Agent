"""
Patient service.

Orchestrates repository calls and enforces business rules for patient
management based on Policy V1:
- Uses phone number as the primary Unique Identifier.
- Enforces uniqueness for phone numbers.
- Handles get-or-create flow for AI agent booking.
- Provides admin methods to remove bans and blacklists.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.patient import Patient
from app.repositories.patient import PatientRepository, patient_repository
from app.schemas.patient import PatientCreate, PatientUpdate

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
        """Retrieve a patient by ID."""
        patient = await self._repo.get_by_id(db, patient_id)
        if patient is None:
            raise NotFoundError("Patient", patient_id)
        return patient

    async def get_patient_by_phone(
        self,
        db: AsyncSession,
        phone: str,
    ) -> Patient:
        """Retrieve a patient by phone number (Unique Identifier).

        Raises:
            NotFoundError: If the patient with this phone does not exist.
        """
        patient = await self._repo.get_by_phone(db, phone)
        if patient is None:
            raise NotFoundError("Patient", phone)
        return patient

    async def list_patients(
        self,
        db: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Patient], int]:
        """Return a paginated list of patients and total count."""
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
            ConflictError: If a patient with the same phone or email already exists.
        """
        # 1. الفحص برقم الهاتف (الـ Unique Identifier الرئيسي)
        existing_phone = await self._repo.get_by_phone(db, data.phone)
        if existing_phone is not None:
            raise ConflictError(f"يوجد مريض مسجل بالفعل برقم الهاتف '{data.phone}'.")

        # 2. الفحص بالإيميل لو كان مدخلاً
        if data.email:
            existing_email = await self._repo.get_by_email(db, data.email)
            if existing_email is not None:
                raise ConflictError(f"يوجد مريض مسجل بالفعل بالبريد الإلكتروني '{data.email}'.")

        patient = await self._repo.create(
            db, data.model_dump(exclude_none=False)
        )
        logger.info("patient_created", patient_id=str(patient.id), phone=data.phone)
        return patient

    async def get_or_create_by_phone(
        self,
        db: AsyncSession,
        phone: str,
        first_name: str,
        last_name: str = "",
    ) -> Patient:
        """Get existing patient by phone or create a new one automatically for booking."""
        patient = await self._repo.get_by_phone(db, phone)
        if patient:
            return patient

        new_data = PatientCreate(
            phone=phone,
            first_name=first_name,
            last_name=last_name or "المحترم",
        )
        patient = await self._repo.create(db, new_data.model_dump(exclude_none=False))
        logger.info("patient_auto_created_on_booking", patient_id=str(patient.id), phone=phone)
        return patient

    async def update_patient(
        self,
        db: AsyncSession,
        patient_id: uuid.UUID,
        data: PatientUpdate,
    ) -> Patient:
        """Apply a partial update to an existing patient."""
        patient = await self.get_patient(db, patient_id)

        # فحص عدم تكرار رقم الهاتف عند التحديث
        if data.phone and data.phone != patient.phone:
            existing_phone = await self._repo.get_by_phone(db, data.phone)
            if existing_phone is not None:
                raise ConflictError(f"رقم الهاتف '{data.phone}' مستخدم بالفعل لمريض آخر.")

        # فحص عدم تكرار الإيميل عند التحديث
        if data.email and data.email != patient.email:
            existing_email = await self._repo.get_by_email(db, data.email)
            if existing_email is not None:
                raise ConflictError(f"البريد الإلكتروني '{data.email}' مستخدم بالفعل لمريض آخر.")

        updated = await self._repo.update(
            db, patient, data.model_dump(exclude_none=True)
        )
        logger.info("patient_updated", patient_id=str(patient_id))
        return updated

    async def unban_patient(
        self,
        db: AsyncSession,
        patient_id: uuid.UUID,
    ) -> Patient:
        """Remove ban and blacklist from a patient (Admin action)."""
        patient = await self.get_patient(db, patient_id)
        
        patient.is_blacklisted = False
        patient.banned_until = None
        patient.no_show_count = 0
        
        updated = await self._repo.update(db, patient, {})
        logger.info("patient_unbanned_by_admin", patient_id=str(patient_id))
        return updated

    async def delete_patient(
        self,
        db: AsyncSession,
        patient_id: uuid.UUID,
    ) -> None:
        """Delete a patient record."""
        patient = await self.get_patient(db, patient_id)
        await self._repo.delete(db, patient)
        logger.info("patient_deleted", patient_id=str(patient_id))


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
patient_service = PatientService()