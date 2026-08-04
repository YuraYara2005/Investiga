"""Unit tests for centralized exception handlers and standard error envelopes."""

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.exceptions import (
    BaseAppException,
    ConflictException,
    NotFoundException,
    RateLimitExceededException,
    UnauthorizedException,
    ValidationException,
    register_exception_handlers,
)


class SamplePayload(BaseModel):
    title: str = Field(..., min_length=3)
    count: int = Field(..., ge=1)


@pytest.fixture
def test_app() -> FastAPI:
    """Create an isolated FastAPI test application with registered exception handlers."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/test/base-app-exception")
    def trigger_base_app_exception():
        raise BaseAppException(
            message="Custom failure occurred.",
            error_code="CUSTOM_FAILURE",
            status_code=400,
            details={"field": "test_param"},
        )

    @app.get("/test/not-found")
    def trigger_not_found():
        raise NotFoundException(
            resource_name="Investigation",
            identifier="inv-uuid-1049",
        )

    @app.get("/test/conflict")
    def trigger_conflict():
        raise ConflictException("Investigation session already active.")

    @app.get("/test/unauthorized")
    def trigger_unauthorized():
        raise UnauthorizedException("Invalid JWT token provided.")

    @app.get("/test/rate-limit")
    def trigger_rate_limit():
        raise RateLimitExceededException(retry_after_seconds=45)

    @app.get("/test/http-exception")
    def trigger_http_exception():
        raise HTTPException(status_code=403, detail="Forbidden operational zone.")

    @app.post("/test/validation")
    def trigger_validation(payload: SamplePayload):
        return {"status": "ok", "received": payload.title}

    @app.get("/test/integrity-error")
    def trigger_integrity_error():
        raise IntegrityError(
            statement="INSERT INTO ...",
            params={},
            orig=Exception("duplicate key value violates unique constraint"),
        )

    @app.get("/test/unhandled-500")
    def trigger_unhandled_500():
        raise ZeroDivisionError("division by zero in calculation")

    return app


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    """TestClient fixture bound to the configured test application."""
    return TestClient(test_app, raise_server_exceptions=False)


def test_base_app_exception_handling(client: TestClient) -> None:
    response = client.get("/test/base-app-exception")
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "CUSTOM_FAILURE"
    assert data["error"]["message"] == "Custom failure occurred."
    assert data["error"]["details"] == {"field": "test_param"}
    assert "timestamp" in data["error"]


def test_not_found_exception_handling(client: TestClient) -> None:
    response = client.get("/test/not-found")
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert (
        data["error"]["message"]
        == "Investigation with identifier 'inv-uuid-1049' was not found."
    )


def test_conflict_exception_handling(client: TestClient) -> None:
    response = client.get("/test/conflict")
    assert response.status_code == 409
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "RESOURCE_CONFLICT"
    assert data["error"]["message"] == "Investigation session already active."


def test_unauthorized_exception_handling(client: TestClient) -> None:
    response = client.get("/test/unauthorized")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_rate_limit_exception_handling(client: TestClient) -> None:
    response = client.get("/test/rate-limit")
    assert response.status_code == 429
    assert response.headers.get("retry-after") == "45"
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert data["error"]["details"]["retry_after_seconds"] == 45


def test_http_exception_handling(client: TestClient) -> None:
    response = client.get("/test/http-exception")
    assert response.status_code == 403
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "PERMISSION_DENIED"
    assert data["error"]["message"] == "Forbidden operational zone."


def test_request_validation_error_handling(client: TestClient) -> None:
    # Send invalid payload (missing count, title too short)
    response = client.post("/test/validation", json={"title": "a"})
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "validation_errors" in data["error"]["details"]
    errors = data["error"]["details"]["validation_errors"]
    assert len(errors) >= 2


def test_sqlalchemy_integrity_error_handling(client: TestClient) -> None:
    response = client.get("/test/integrity-error")
    assert response.status_code == 409
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "RESOURCE_CONFLICT"
    assert "duplicate key" not in data["error"]["message"]  # Raw SQL info not leaked


def test_unhandled_exception_handling(client: TestClient) -> None:
    response = client.get("/test/unhandled-500")
    assert response.status_code == 500
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "division by zero" not in data["error"]["message"]  # Internal trace not leaked


def test_trace_id_header_propagation(client: TestClient) -> None:
    response = client.get(
        "/test/not-found", headers={"X-Request-ID": "test-req-9041"}
    )
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["trace_id"] == "test-req-9041"
