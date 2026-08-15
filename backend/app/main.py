"""
FastAPI application factory / main entry point (Production-Ready).

Configures:
  1. Dynamic CORS for Production & Local environments.
  2. Safe Rate Limiting for Chat interactions (SlowAPI).
  3. Structured Request Logging & Request-ID Tracing.
  4. Automatic DB Tables creation & First Admin Seeder.
  5. Global Exception Handlers.
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError as PydanticValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import select

from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.core.constants import API_V1_PREFIX, HEALTH_CHECK_PATH
from app.core.exceptions import AppException
from app.core.logging import setup_logging
from app.core.security import hash_password
from app.database.base import AsyncSessionFactory, Base, engine

# ── Explicit Model Imports for Table Registration ────────────────────────────
from app.models.ai_usage import AIUsageLog
from app.models.appointment import Appointment
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User, UserRole
from app.schemas.common import ErrorResponse

logger = structlog.get_logger(__name__)

# =============================================================================
# Rate Limiter Configuration (Safe for Real-Time Chatting)
# =============================================================================

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/10minutes"],  # معدل متزن ومناسب للشات
)


# =============================================================================
# Automatic First Clinic & Admin Seeder
# =============================================================================

async def _auto_seed_first_admin() -> None:
    """إنشاء العيادة الافتراضية وحساب الأدمن الأول عند الإقلاع تلقائياً."""
    if not getattr(settings, "ADMIN_USERNAME", None) or not getattr(settings, "ADMIN_PASSWORD", None):
        logger.info("admin_seed_skipped_no_env_vars")
        return

    try:
        async with AsyncSessionFactory() as db:
            # 1. فحص وجود العيادة الافتراضية
            stmt_clinic = select(Clinic).where(Clinic.slug == "main-clinic")
            res_clinic = await db.execute(stmt_clinic)
            clinic = res_clinic.scalar_one_or_none()

            if not clinic:
                clinic = Clinic(
                    name="العيادة التخصصية للأسنان",
                    slug="main-clinic",
                    phone="01000000000",
                    address="المقر الرئيسي للعيادة",
                    is_active=True,
                )
                db.add(clinic)
                await db.flush()

            # 2. فحص وجود حساب أدمن
            stmt = select(User).where(User.role == UserRole.ADMIN)
            res = await db.execute(stmt)
            existing_admin = res.scalar_one_or_none()

            if not existing_admin:
                first_admin = User(
                    clinic_id=clinic.id,
                    username=settings.ADMIN_USERNAME,
                    full_name="مدير النظام الرئيسي",
                    hashed_password=hash_password(settings.ADMIN_PASSWORD),
                    role=UserRole.ADMIN,
                    is_active=True,
                )
                db.add(first_admin)
                await db.commit()
                logger.info(
                    "first_admin_auto_seeded",
                    username=settings.ADMIN_USERNAME,
                    clinic_id=str(clinic.id),
                )
    except Exception as exc:
        logger.warning("auto_seed_admin_failed", error=str(exc))


# =============================================================================
# Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup → yield → shutdown."""
    setup_logging()
    logger.info(
        "application_starting",
        name=settings.app_name,
        version=settings.app_version,
        env=settings.app_env,
    )

    try:
        # 1. إنشاء الجداول
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        created_tables = list(Base.metadata.tables.keys())
        logger.info("database_tables_created_ok", tables=created_tables)

        # 2. تشغيل الـ Seeder
        await _auto_seed_first_admin()

    except Exception as exc:
        logger.error("database_initialization_failed", error=str(exc))
        raise

    yield

    logger.info("application_shutdown")
    await engine.dispose()


# =============================================================================
# App Factory
# =============================================================================

def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""
    is_prod = getattr(settings, "ENVIRONMENT", "").lower() == "production"

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI-powered multi-tenant virtual receptionist and administration system.",
        docs_url=None if is_prod else "/docs",  # إخفاء الـ Docs في الإنتاج لحماية الباك إند
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
        lifespan=lifespan,
    )

    app.state.limiter = limiter

    _register_middleware(app)
    _register_exception_handlers(app)
    _register_routers(app)

    # Mount Dashboard Frontend Static Files
    _dashboard_dir = Path(__file__).parent.parent / "dashboard-frontend"
    if _dashboard_dir.is_dir():
        app.mount("/dashboard", StaticFiles(directory=str(_dashboard_dir), html=True), name="dashboard")

    return app


# =============================================================================
# Middleware
# =============================================================================

def _register_middleware(app: FastAPI) -> None:
    """Attach all middleware to the application."""

    # 1. إعدادات CORS المتوافقة مع الإنتاج والمحلي
    allowed_origins = getattr(
        settings,
        "CORS_ORIGINS",
        [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins if isinstance(allowed_origins, list) else ["*"],
        allow_origin_regex=r"https://.*\.vercel\.app" if allowed_origins == ["*"] else None,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Structured Request Logging & Request-ID
    @app.middleware("http")
    async def logging_middleware(request: Request, call_next: object) -> object:
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        response.headers["X-Request-ID"] = request_id
        return response


# =============================================================================
# Exception Handlers
# =============================================================================

def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers."""
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.warning(
            "app_exception",
            error_type=type(exc).__name__,
            message=exc.message,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=type(exc).__name__,
                message=exc.message,
                detail=exc.detail,
            ).model_dump(),
        )

    @app.exception_handler(PydanticValidationError)
    async def pydantic_exception_handler(request: Request, exc: PydanticValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error="ValidationError",
                message="Request validation failed.",
                detail=exc.errors(),
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", path=request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="InternalServerError",
                message="An unexpected error occurred. Please try again later.",
                detail=None,
            ).model_dump(),
        )


# =============================================================================
# Routers
# =============================================================================

def _register_routers(app: FastAPI) -> None:
    """Mount all routers onto the application."""

    @app.get(
        HEALTH_CHECK_PATH,
        tags=["Health"],
        summary="Liveness probe",
        description="Returns 200 OK if the application is running.",
    )
    async def health_check() -> dict[str, str]:
        return {
            "status": "ok",
            "service": settings.app_name,
            "version": settings.app_version,
            "environment": getattr(settings, "ENVIRONMENT", "development"),
        }

    app.include_router(api_v1_router, prefix=API_V1_PREFIX)


# =============================================================================
# App Instance
# =============================================================================

app = create_app()