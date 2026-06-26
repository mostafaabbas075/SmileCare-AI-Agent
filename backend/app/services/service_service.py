"""
Service (dental treatment) service layer.

Named ``ServiceService`` to distinguish the *service layer* class from
the *dental service* domain entity — a common naming tension in this domain.
"""

from __future__ import annotations

import uuid

import structlog

from app.core.exceptions import ConflictError, NotFoundError
from app.models.service import Service
from app.repositories.service import ServiceRepository, service_repository
from app.schemas.service import ServiceCreate, ServiceUpdate
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class ServiceService:
    """Business logic for dental service / treatment management."""

    def __init__(self, repo: ServiceRepository = service_repository) -> None:
        self._repo = repo

    async def get_service(
        self,
        db: AsyncSession,
        service_id: uuid.UUID,
    ) -> Service:
        """Retrieve a service by ID.

        Raises:
            NotFoundError: If the service does not exist.
        """
        service = await self._repo.get_by_id(db, service_id)
        if service is None:
            raise NotFoundError("Service", service_id)
        return service

    async def list_services(
        self,
        db: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Service], int]:
        """Return a paginated list of services and total count."""
        services = await self._repo.get_all(db, offset=offset, limit=limit)
        total = await self._repo.count(db)
        return services, total

    async def create_service(
        self,
        db: AsyncSession,
        data: ServiceCreate,
    ) -> Service:
        """Create a new dental service.

        Raises:
            ConflictError: If a service with the same name already exists.
        """
        existing = await self._repo.get_by_name(db, data.name)
        if existing is not None:
            raise ConflictError(f"A service named '{data.name}' already exists.")

        service = await self._repo.create(db, data.model_dump())
        logger.info("service_created", service_id=str(service.id), name=service.name)
        return service

    async def update_service(
        self,
        db: AsyncSession,
        service_id: uuid.UUID,
        data: ServiceUpdate,
    ) -> Service:
        """Apply a partial update to a service.

        Raises:
            NotFoundError: If the service does not exist.
            ConflictError: If the new name is already taken.
        """
        service = await self.get_service(db, service_id)

        if data.name and data.name != service.name:
            existing = await self._repo.get_by_name(db, data.name)
            if existing is not None:
                raise ConflictError(f"A service named '{data.name}' already exists.")

        updated = await self._repo.update(db, service, data.model_dump(exclude_none=True))
        logger.info("service_updated", service_id=str(service_id))
        return updated

    async def delete_service(
        self,
        db: AsyncSession,
        service_id: uuid.UUID,
    ) -> None:
        """Delete a service.

        Raises:
            NotFoundError: If the service does not exist.
        """
        service = await self.get_service(db, service_id)
        await self._repo.delete(db, service)
        logger.info("service_deleted", service_id=str(service_id))


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
service_service = ServiceService()
