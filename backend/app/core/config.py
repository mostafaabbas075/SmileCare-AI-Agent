"""
Application configuration.

All runtime configuration is loaded from environment variables via Pydantic
BaseSettings. This is the single source of truth for config — no scattered
``os.getenv()`` calls anywhere else in the codebase.

Usage::

    from app.core.config import settings

    print(settings.database_url)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration object backed by environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "AI Dental Clinic Receptionist"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # -------------------------------------------------------------------------
    # API
    # -------------------------------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_prefix: str = "/api/v1"
    # تم إضافة 127.0.0.1 لتجنب مشاكل الـ CORS في المتصفح
    allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173"]

    # -------------------------------------------------------------------------
    # Security
    # -------------------------------------------------------------------------
    secret_key: str = Field(min_length=32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)

    # -------------------------------------------------------------------------
    # PostgreSQL (individual parts — URL assembled by computed_field)
    # -------------------------------------------------------------------------
    postgres_host: str = "localhost"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = "dental_receptionist"
    postgres_user: str = "dental_user"
    postgres_password: str

    # -------------------------------------------------------------------------
    # Qdrant
    # -------------------------------------------------------------------------
    qdrant_host: str = "localhost"
    qdrant_port: int = Field(default=6333, ge=1, le=65535)
    qdrant_collection_name: str = "dental_knowledge"

    # -------------------------------------------------------------------------
    # Google Gemini
    # -------------------------------------------------------------------------
    # تم تغيير الاسم هنا ليطابق الكود في ملف dental_agent.py
    GOOGLE_API_KEY: str
    gemini_model: str = "gemini-2.5-flash"

    # -------------------------------------------------------------------------
    # Sentence Transformers
    # -------------------------------------------------------------------------
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = Field(default=384, ge=1)

    # -------------------------------------------------------------------------
    # Computed fields (not read from .env)
    # -------------------------------------------------------------------------
    @computed_field  # type: ignore[misc]
    @property
    def QDRANT_URL(self) -> str:
        """تمت الإضافة: رابط Qdrant ديناميكي ليستخدمه الـ Retriever."""
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    @computed_field  # type: ignore[misc]
    @property
    def database_url(self) -> str:
        """Async-compatible PostgreSQL DSN using asyncpg driver."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def database_url_sync(self) -> str:
        """Synchronous PostgreSQL DSN using psycopg2 (for Alembic)."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def is_production(self) -> bool:
        """Convenience flag for production-specific behaviour."""
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton.

    Using ``lru_cache`` ensures the settings object (and its .env parsing) is
    only created once per process, even if ``get_settings()`` is called from
    multiple modules.
    """
    return Settings()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere
# ---------------------------------------------------------------------------
settings: Settings = get_settings()