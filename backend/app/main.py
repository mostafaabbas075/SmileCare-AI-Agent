"""
FastAPI application factory.

This module:

  1. Creates the FastAPI app instance with metadata.
  2. Registers middleware (CORS, request logging, timing).
  3. Registers the global exception handler.
  4. Mounts the v1 API router.
  5. Exposes a ``/health`` liveness probe.

Lifespan
--------
The ``lifespan`` context manager runs startup and shutdown logic:

  - Startup:  configure logging, validate DB connectivity.
  - Shutdown: dispose the SQLAlchemy connection pool.

Global Exception Handler
------------------------
Catches all ``AppException`` subclasses and returns a consistent
``ErrorResponse`` JSON envelope. Pydantic ``ValidationError`` is also
caught and re-shaped to match the same envelope.
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.core.constants import API_V1_PREFIX, HEALTH_CHECK_PATH
from app.core.exceptions import AppException
from app.core.logging import setup_logging
from app.database.base import engine
from app.schemas.common import ErrorResponse

logger = structlog.get_logger(__name__)


# =============================================================================
# Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup → yield → shutdown."""

    # ── Startup ───────────────────────────────────────────────────────────
    setup_logging()
    logger.info(
        "application_starting",
        name=settings.app_name,
        version=settings.app_version,
        env=settings.app_env,
    )

    # Validate DB is reachable by establishing one connection
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        logger.info("database_connection_ok")
    except Exception as exc:  # pragma: no cover
        logger.error("database_connection_failed", error=str(exc))
        raise

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────
    logger.info("application_shutdown")
    await engine.dispose()


# =============================================================================
# App factory
# =============================================================================

def create_app() -> FastAPI:
    """Construct and configure the FastAPI application.

    Kept as a factory function (rather than a module-level assignment) to
    make it easy to create test-isolated app instances.
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "AI-powered virtual receptionist for a modern dental clinic. "
            "Provides REST APIs for patient management, appointment booking, "
            "and AI-driven chat."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    _register_middleware(app)
    _register_exception_handlers(app)
    _register_routers(app)

    return app


# =============================================================================
# Middleware
# =============================================================================

def _register_middleware(app: FastAPI) -> None:
    """Attach all middleware to the application."""

    # CORS — allow configured origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging + timing middleware
    @app.middleware("http")
    async def logging_middleware(request: Request, call_next: object) -> object:  # type: ignore[type-arg]
        """Log every request with method, path, status, and duration."""
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        # Bind request_id to the structlog context for this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)  # type: ignore[operator]

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

    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request,
        exc: AppException,
    ) -> JSONResponse:
        """Map custom AppException subclasses to consistent JSON responses."""
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
    async def pydantic_exception_handler(
        request: Request,
        exc: PydanticValidationError,
    ) -> JSONResponse:
        """Re-shape Pydantic validation errors into the standard envelope."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error="ValidationError",
                message="Request validation failed.",
                detail=exc.errors(),
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Catch-all for any unexpected exceptions — never expose stack traces."""
        logger.exception("unhandled_exception", path=request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="InternalServerError",
                message="An unexpected error occurred. Please try again later.",
            ).model_dump(),
        )


# =============================================================================
# Routers
# =============================================================================

def _register_routers(app: FastAPI) -> None:
    """Mount all routers onto the application."""

    # Health check — mounted directly (no version prefix)
    @app.get(
        HEALTH_CHECK_PATH,
        tags=["Health"],
        summary="Liveness probe",
        description="Returns 200 OK if the application is running. Used by Docker/Kubernetes health checks.",
    )
    async def health_check() -> dict[str, str]:
        return {
            "status": "ok",
            "service": settings.app_name,
            "version": settings.app_version,
            "environment": settings.app_env,
        }

    # v1 API
    app.include_router(api_v1_router, prefix=API_V1_PREFIX)


# =============================================================================
# App instance (imported by uvicorn)
# =============================================================================

app = create_app()
