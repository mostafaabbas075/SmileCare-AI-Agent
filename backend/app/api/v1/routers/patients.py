"""
Patients router.

Provides full CRUD endpoints for patient management, searching by phone number,
and unbanning patients who were restricted under Policy V1 rules.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Request, status
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
    "/by-phone/{phone}",
    response_model=PatientResponse,
    summary="Get patient by phone number",
    description="Retrieve a patient by phone number (Unique Identifier in Policy V1).",
)
async def get_patient_by_phone(
    phone: str,
    db: AsyncSession = Depends(get_db),
) -> PatientResponse:
    """Return a single patient by phone number."""
    patient = await patient_service.get_patient_by_phone(db, phone)
    return PatientResponse.model_validate(patient)


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
    request: Request,
    data: PatientCreate,
    db: AsyncSession = Depends(get_db),
) -> PatientResponse:
    """Create a new patient record."""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    patient = await patient_service.create_patient(db, data)

    logger.info(
        "audit_patient_created",
        patient_id=str(patient.id),
        phone=patient.phone,
        ip_address=client_ip,
        user_agent=user_agent,
        action="CREATE_PATIENT",
        timestamp=datetime.now(UTC).isoformat(),
    )

    return PatientResponse.model_validate(patient)


@router.put(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Update patient information",
)
async def update_patient(
    request: Request,
    patient_id: uuid.UUID,
    data: PatientUpdate,
    db: AsyncSession = Depends(get_db),
) -> PatientResponse:
    """Apply a partial update to a patient record."""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    patient = await patient_service.update_patient(db, patient_id, data)

    logger.info(
        "audit_patient_updated",
        patient_id=str(patient_id),
        ip_address=client_ip,
        user_agent=user_agent,
        action="UPDATE_PATIENT",
        timestamp=datetime.now(UTC).isoformat(),
    )

    return PatientResponse.model_validate(patient)


@router.post(
    "/{patient_id}/unban",
    response_model=PatientResponse,
    summary="Unban patient / Remove from blacklist",
    description="Action for clinic staff to remove bans, clear blacklists, and reset No-Show counters for a patient.",
)
async def unban_patient(
    request: Request,
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PatientResponse:
    """Remove bans and reset No-Show status for a patient."""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    patient = await patient_service.unban_patient(db, patient_id)

    logger.info(
        "audit_patient_unbanned",
        patient_id=str(patient_id),
        ip_address=client_ip,
        user_agent=user_agent,
        action="UNBAN_PATIENT",
        timestamp=datetime.now(UTC).isoformat(),
    )

    return PatientResponse.model_validate(patient)


@router.delete(
    "/{patient_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a patient",
)
async def delete_patient(
    request: Request,
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Delete a patient record and all associated data."""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    await patient_service.delete_patient(db, patient_id)

    logger.info(
        "audit_patient_deleted",
        patient_id=str(patient_id),
        ip_address=client_ip,
        user_agent=user_agent,
        action="DELETE_PATIENT",
        timestamp=datetime.now(UTC).isoformat(),
    )

    return MessageResponse(message=f"Patient {patient_id} deleted successfully.")