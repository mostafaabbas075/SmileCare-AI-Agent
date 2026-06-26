"""
Database session dependency.

Provides a per-request ``AsyncSession`` that is:

  1. Created at the start of the request.
  2. Committed on success.
  3. Rolled back automatically on exception.
  4. Closed when the request completes.

Usage in a router::

    @router.post("/patients")
    async def create_patient(
        data: PatientCreate,
        db: AsyncSession = Depends(get_db),
    ) -> PatientResponse:
        ...
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import AsyncSessionFactory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a managed async database session.

    The session is committed if the request handler returns without raising,
    rolled back otherwise, and always closed on exit.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
