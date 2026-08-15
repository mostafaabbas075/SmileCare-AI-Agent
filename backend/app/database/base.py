from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
# 👈 استيراد Base الأصلي اللي بتستورد منه الموديلات (مثل user.py)
from app.database.base_model import Base


# Async Engine
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
)


# Session Factory
AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


# 👈 استيراد كافة الموديلز لربط الجداول بنفس الـ Base.metadata
import app.models.user  # noqa: F401
import app.models.patient  # noqa: F401
import app.models.doctor  # noqa: F401
import app.models.service  # noqa: F401
import app.models.appointment  # noqa: F401