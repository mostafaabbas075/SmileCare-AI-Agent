"""
Smoke tests for application startup.

These tests verify that:
  1. The FastAPI app starts without errors.
  2. The /health endpoint returns 200.
  3. The OpenAPI schema is accessible.
  4. All expected API routes are registered.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_check(client: TestClient) -> None:
    """GET /health → 200 with expected keys."""
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "environment" in body


def test_openapi_schema_accessible(client: TestClient) -> None:
    """GET /openapi.json → 200 — confirms all routers loaded without import errors."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "AI Dental Clinic Receptionist"


def test_api_routes_registered(client: TestClient) -> None:
    """Verify all expected route prefixes are present in the OpenAPI schema."""
    response = client.get("/openapi.json")
    paths = response.json()["paths"]
    expected_prefixes = [
        "/api/v1/patients",
        "/api/v1/doctors",
        "/api/v1/services",
        "/api/v1/appointments",
        "/api/v1/chat",
        "/api/v1/documents",
    ]
    for prefix in expected_prefixes:
        matching = [p for p in paths if p.startswith(prefix)]
        assert matching, f"No routes found with prefix: {prefix}"
