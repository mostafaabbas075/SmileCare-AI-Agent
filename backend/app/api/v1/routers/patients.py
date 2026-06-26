"""
Patients router.

Provides full CRUD endpoints for patient management.
All endpoints are async and use FastAPI's dependency injection for the
database session and pagination parameters.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.patient import PatientCreate, PatientResponse, PatientUpdate
from app.services.patient_service import patient_service
from app.utils.pagination import PaginationDep

router = APIRouter(prefix="/patients", tags=["Patients"])
logger = structlog.get_logger(__name__)


@router.get(
    "",
    response_model=PaginatedResponse[PatientResponse],
    summary="List all patients",
    description="Returns a paginated list of all registered patients.",
)
async def list_patients(
    pagination: PaginationDep,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[PatientResponse]:
    """Return a paginated list of patients."""
    patients, total = await patient_service.list_patients(
        db,
        offset=pagination.offset,
        limit=pagination.page_size,
    )
    return PaginatedResponse.create(
        data=[PatientResponse.model_validate(p) for p in patients],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Get patient by ID",
)
async def get_patient(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PatientResponse:
    """Return a single patient by UUID."""
    patient = await patient_service.get_patient(db, patient_id)
    return PatientResponse.model_validate(patient)


@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new patient",
)
async def create_patient(
    data: PatientCreate,
    db: AsyncSession = Depends(get_db),
) -> PatientResponse:
    """Create a new patient record."""
    patient = await patient_service.create_patient(db, data)
    return PatientResponse.model_validate(patient)


@router.put(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Update patient information",
)
async def update_patient(
    patient_id: uuid.UUID,
    data: PatientUpdate,
    db: AsyncSession = Depends(get_db),
) -> PatientResponse:
    """Apply a partial update to a patient record."""
    patient = await patient_service.update_patient(db, patient_id, data)
    return PatientResponse.model_validate(patient)


@router.delete(
    "/{patient_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a patient",
)
async def delete_patient(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Delete a patient record and all associated data."""
    await patient_service.delete_patient(db, patient_id)
    return MessageResponse(message=f"Patient {patient_id} deleted successfully.")
