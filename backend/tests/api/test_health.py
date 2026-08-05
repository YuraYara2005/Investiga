"""Integration tests for API routing, application factory, middleware, and health probes."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_database
from app.main import create_app


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session that resolves SELECT 1 successfully."""
    session = AsyncMock()
    session.execute.return_value = AsyncMock()
    return session


@pytest.fixture
def client(mock_db_session: AsyncMock) -> TestClient:
    """Instantiate a TestClient with overridden database dependency."""
    app = create_app()

    async def override_get_database() -> AsyncGenerator[AsyncMock, None]:
        yield mock_db_session

    app.dependency_overrides[get_database] = override_get_database
    return TestClient(app, raise_server_exceptions=False)


def test_liveness_probe(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "timestamp" in data


def test_readiness_probe_success(client: TestClient) -> None:
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "database" in data["components"]
    assert data["components"]["database"]["status"] == "healthy"
    assert "latency_ms" in data["components"]["database"]


def test_readiness_probe_failure(mock_db_session: AsyncMock) -> None:
    # Configure mock to raise a database exception
    mock_db_session.execute.side_effect = Exception("PostgreSQL connection refused")

    app = create_app()

    async def override_failed_db() -> AsyncGenerator[AsyncMock, None]:
        yield mock_db_session

    app.dependency_overrides[get_database] = override_failed_db
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "SERVICE_UNAVAILABLE"


def test_comprehensive_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["application"] == "Investiga"
    assert "version" in data
    assert "environment" in data
    assert "components" in data
    assert "database" in data["components"]


def test_root_health_alias(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["application"] == "Investiga"


def test_middleware_request_id_and_timing_injection(client: TestClient) -> None:
    custom_trace_id = "custom-trace-id-12345"
    response = client.get(
        "/api/v1/health/live", headers={"X-Request-ID": custom_trace_id}
    )
    assert response.status_code == 200
    assert response.headers.get("x-request-id") == custom_trace_id
    assert "x-process-time-ms" in response.headers


def test_openapi_schema_endpoint(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Investiga API"
    assert "/api/v1/health" in schema["paths"]
    assert "/api/v1/health/live" in schema["paths"]
    assert "/api/v1/health/ready" in schema["paths"]


def test_swagger_and_redoc_ui_endpoints(client: TestClient) -> None:
    docs_response = client.get("/docs")
    assert docs_response.status_code == 200
    assert "swagger-ui" in docs_response.text.lower()

    redoc_response = client.get("/redoc")
    assert redoc_response.status_code == 200
    assert "redoc" in redoc_response.text.lower()
