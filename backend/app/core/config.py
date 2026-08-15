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
from typing import Literal, Optional

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
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
    ]

    # -------------------------------------------------------------------------
    # Security & Auth
    # -------------------------------------------------------------------------
    secret_key: str = Field(default="SmileCare_Super_Secret_Key_Change_In_Production_2026", min_length=32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=720, ge=1)  # 12 Hours
    refresh_token_expire_days: int = Field(default=7, ge=1)

    # -------------------------------------------------------------------------
    # Initial Admin Seeding (First Deployment Credentials via Environment)
    # -------------------------------------------------------------------------
    admin_username: str = "admin"
    admin_password: str = "ChangeThisStrongPassword2026!"

    # -------------------------------------------------------------------------
    # PostgreSQL (Neon Cloud Compatible)
    # -------------------------------------------------------------------------
    postgres_host: str = "localhost"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = "dental_receptionist"
    postgres_user: str = "dental_user"
    postgres_password: str = "dental_pass"

    # -------------------------------------------------------------------------
    # Qdrant (Supports both local & Cloud via HTTPS + API Key)
    # -------------------------------------------------------------------------
    qdrant_host: str = "localhost"
    qdrant_port: int = Field(default=6333, ge=1, le=65535)
    qdrant_api_key: Optional[str] = None
    qdrant_collection_name: str = "dental_knowledge"

    # -------------------------------------------------------------------------
    # Google Gemini
    # -------------------------------------------------------------------------
    GOOGLE_API_KEY: str = "dummy_gemini_key"
    gemini_model: str = "gemini-3.5-flash-lite"

    # -------------------------------------------------------------------------
    # Sentence Transformers
    # -------------------------------------------------------------------------
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = Field(default=384, ge=1)

    # -------------------------------------------------------------------------
    # Aliases & Properties for Uppercase compatibility across the App
    # -------------------------------------------------------------------------
    @property
    def ADMIN_USERNAME(self) -> str:
        return self.admin_username

    @property
    def ADMIN_PASSWORD(self) -> str:
        return self.admin_password

    @property
    def GEMINI_MODEL(self) -> str:
        return self.gemini_model

    @property
    def QDRANT_HOST(self) -> str:
        return self.qdrant_host

    @property
    def QDRANT_API_KEY(self) -> Optional[str]:
        return self.qdrant_api_key

    @property
    def QDRANT_COLLECTION_NAME(self) -> str:
        return self.qdrant_collection_name

    # -------------------------------------------------------------------------
    # Computed fields (not read from .env)
    # -------------------------------------------------------------------------
    @computed_field  # type: ignore[misc]
    @property
    def database_url(self) -> str:
        """Async-compatible PostgreSQL DSN supporting local & Neon SSL."""
        url = (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        if "neon.tech" in self.postgres_host:
            url += "?ssl=require"  # 👈 SSL الخاص بـ asyncpg
        return url

    @computed_field  # type: ignore[misc]
    @property
    def is_production(self) -> bool:
        """Convenience flag for production-specific behaviour."""
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    return Settings()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere
# ---------------------------------------------------------------------------
settings: Settings = get_settings()