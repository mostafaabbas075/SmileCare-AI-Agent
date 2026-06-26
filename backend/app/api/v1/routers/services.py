"""
Services router.

Provides CRUD endpoints for dental treatment / service management.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.service import ServiceCreate, ServiceResponse, ServiceUpdate
from app.services.service_service import service_service
from app.utils.pagination import PaginationDep

router = APIRouter(prefix="/services", tags=["Services"])


@router.get(
    "",
    response_model=PaginatedResponse[ServiceResponse],
    summary="List all dental services",
)
async def list_services(
    pagination: PaginationDep,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ServiceResponse]:
    """Return a paginated list of all dental services and treatments."""
    services, total = await service_service.list_services(
        db,
        offset=pagination.offset,
        limit=pagination.page_size,
    )
    return PaginatedResponse.create(
        data=[ServiceResponse.model_validate(s) for s in services],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/{service_id}",
    response_model=ServiceResponse,
    summary="Get service by ID",
)
async def get_service(
    service_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ServiceResponse:
    """Return a single service by UUID."""
    service = await service_service.get_service(db, service_id)
    return ServiceResponse.model_validate(service)


@router.post(
    "",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new dental service",
)
async def create_service(
    data: ServiceCreate,
    db: AsyncSession = Depends(get_db),
) -> ServiceResponse:
    """Create a new dental service record."""
    service = await service_service.create_service(db, data)
    return ServiceResponse.model_validate(service)


@router.put(
    "/{service_id}",
    response_model=ServiceResponse,
    summary="Update a dental service",
)
async def update_service(
    service_id: uuid.UUID,
    data: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
) -> ServiceResponse:
    """Apply a partial update to a service record."""
    service = await service_service.update_service(db, service_id, data)
    return ServiceResponse.model_validate(service)


@router.delete(
    "/{service_id}",
    response_model=MessageResponse,
    summary="Delete a dental service",
)
async def delete_service(
    service_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Delete a service record."""
    await service_service.delete_service(db, service_id)
    return MessageResponse(message=f"Service {service_id} deleted successfully.")
