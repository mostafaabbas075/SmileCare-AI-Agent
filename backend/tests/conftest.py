"""
Test configuration and shared fixtures.

Uses pytest-asyncio in auto mode. The ``test_db`` fixture creates an
in-memory SQLite database for unit tests (no PostgreSQL required) and
rolls back after each test, ensuring test isolation.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def client() -> TestClient:
    """Synchronous test client for simple smoke tests."""
    return TestClient(app)


@pytest.fixture
async def async_client() -> AsyncClient:
    """Async test client for testing async endpoints."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
