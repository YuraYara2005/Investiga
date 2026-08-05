"""Standardized Error Response Models for Investiga.

This module defines the canonical Pydantic v2 schemas and builder utilities for all
error responses emitted across the Investiga REST API. It guarantees a deterministic,
machine-readable JSON contract for frontend and API consumers.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Detailed error payload encapsulating machine-readable and diagnostic metadata."""

    code: str = Field(
        ...,
        description="Machine-readable error classification code (e.g., RESOURCE_NOT_FOUND).",
        examples=["RESOURCE_NOT_FOUND"],
    )
    message: str = Field(
        ...,
        description="Human-readable explanation of the error condition.",
        examples=["The requested investigation session was not found."],
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Contextual diagnostic payload or field-level validation errors.",
    )
    trace_id: str | None = Field(
        default=None,
        description="Correlation or request identifier for distributed tracing and log lookup.",
        examples=["req-7a9b-4c2d-98e1"],
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO 8601 UTC timestamp when the error occurred.",
        examples=["2026-08-05T01:30:00.000000Z"],
    )


class ErrorResponse(BaseModel):
    """Envelope wrapper for all API failure responses."""

    success: bool = Field(
        default=False,
        description="Indicator of operation success (always false for error envelopes).",
    )
    error: ErrorDetail = Field(
        ...,
        description="Structured error details.",
    )


def create_error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    trace_id: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Construct a standardized JSONResponse using the canonical ErrorResponse schema.

    Args:
        status_code: HTTP status code (e.g., 400, 404, 500).
        code: Machine-readable error code.
        message: Human-readable explanation.
        details: Optional field-level errors or diagnostic context.
        trace_id: Optional correlation/request identifier.
        headers: Optional HTTP headers (e.g. WWW-Authenticate, Retry-After).

    Returns:
        JSONResponse: Structured HTTP response matching the ErrorResponse contract.
    """
    error_payload = ErrorResponse(
        success=False,
        error=ErrorDetail(
            code=code,
            message=message,
            details=details or {},
            trace_id=trace_id,
            timestamp=datetime.now(UTC).isoformat(),
        ),
    )

    return JSONResponse(
        status_code=status_code,
        content=error_payload.model_dump(),
        headers=headers,
    )
