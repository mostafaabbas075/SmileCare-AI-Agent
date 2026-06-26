"""
SQLAlchemy async engine and session factory.

This module creates a single async engine and session factory that are shared
across the entire application. The session is not created here — it is yielded
per-request by the ``get_db`` dependency in ``app/dependencies/database.py``.

Design decisions:

- ``NullPool`` is NOT used (we want connection pooling in production).
- ``pool_pre_ping=True`` detects stale connections before use, preventing
  "server closed the connection unexpectedly" errors.
- ``echo=False`` in production; can be toggled via settings for debugging.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,          # log SQL statements when DEBUG=true
    pool_pre_ping=True,           # validate connections before checkout
    pool_size=10,                 # max number of connections in pool
    max_overflow=20,              # extra connections above pool_size
    pool_recycle=3600,            # recycle connections after 1 hour
)

# ---------------------------------------------------------------------------
# Session Factory
# ---------------------------------------------------------------------------
AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,       # objects stay usable after commit
    autocommit=False,
    autoflush=False,
)
