from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.database.base_model import Base


# Async Engine with Auto-Reconnect and Pool Pre-Ping
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,      # يفحص الاتصال قبل كل استعلام ويعيد الاتصال تلقائياً إذا كان مغلقاً
    pool_recycle=300,        # تجديد الاتصالات كل 5 دقائق لمنع قطع الاتصال من طرف مزود قاعدة البيانات
    pool_size=10,            # عدد الاتصالات الأساسية في المجمع
    max_overflow=20,         # الاتصالات الإضافية وقت الذروة
)


# Session Factory
AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


# استيراد كافة الموديلز لربط الجداول بنفس الـ Base.metadata
import app.models.ai_usage  # noqa: F401
import app.models.appointment  # noqa: F401
import app.models.clinic  # noqa: F401
import app.models.conversation_history  # noqa: F401
import app.models.doctor  # noqa: F401
import app.models.knowledge_document  # noqa: F401
import app.models.patient  # noqa: F401
import app.models.service  # noqa: F401
import app.models.user  # noqa: F401