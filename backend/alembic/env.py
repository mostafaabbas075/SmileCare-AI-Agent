"""
Alembic environment configuration.

This module bridges the Alembic migration system with the application's
SQLAlchemy setup. It:

  1. Imports all ORM models so Alembic's autogenerate can detect schema changes.
  2. Reads the DATABASE_URL from the application's Pydantic settings, ensuring
     a single source of truth for configuration.
  3. Supports both online (connected) and offline (SQL script) migration modes.

The async engine is run synchronously inside Alembic by using
``run_sync`` on a sync-compatible connection URL (asyncpg → psycopg2).
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ---------------------------------------------------------------------------
# App imports — ORDER MATTERS
# ---------------------------------------------------------------------------
# 1. Import settings first (needed for DATABASE_URL)
from app.core.config import settings

# 2. Import the declarative base so metadata is populated
from app.database.base_model import Base

# 3. Import ALL models so they register themselves on Base.metadata
import app.models  # noqa: F401  (side-effect import)

# ---------------------------------------------------------------------------
# Alembic Config object (gives access to alembic.ini values)
# ---------------------------------------------------------------------------
config = context.config

# Set up Python logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url with the value from our Pydantic settings.
# # Alembic requires a synchronous URL; we swap the asyncpg driver for psycopg2.
# sync_url = settings.database_url.replace("asyncpg", "psycopg2")
sync_url = str(settings.database_url)
config.set_main_option("sqlalchemy.url", sync_url)

# The metadata object Alembic uses for --autogenerate
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline mode — generate SQL script without a live connection
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.  Calls to
    context.execute() emit the given string to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,       # detect column type changes
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode — run migrations against a live database
# ---------------------------------------------------------------------------
def do_run_migrations(connection: Connection) -> None:
    """Execute migrations on an active connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations on its sync-compatible connection."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migration mode."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
