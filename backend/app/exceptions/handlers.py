"""Centralized Exception Handlers for FastAPI in Investiga.

This module intercepts domain exceptions, HTTP errors, request validation failures,
SQLAlchemy database errors, and unexpected internal crashes. It converts them into
consistent, schema-compliant JSON error envelopes while preserving full diagnostic
telemetry in Structlog.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger
from app.exceptions.base import BaseAppException
from app.exceptions.responses import create_error_response

logger = get_logger(__name__)


def _extract_trace_id(request: Request) -> str | None:
    """Safely extract request/correlation trace ID from request state."""
    return getattr(request.state, "request_id", None) or request.headers.get(
        "X-Request-ID"
    )


async def app_exception_handler(
    request: Request, exc: BaseAppException
) -> Any:
    """Handle custom application and domain exceptions."""
    trace_id = _extract_trace_id(request)

    if exc.status_code >= 500:
        logger.error(
            "app_exception_raised",
            error_code=exc.error_code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
            path=str(request.url.path),
            method=request.method,
            trace_id=trace_id,
            exc_info=True,
        )
    else:
        logger.warning(
            "domain_exception_handled",
            error_code=exc.error_code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
            path=str(request.url.path),
            method=request.method,
            trace_id=trace_id,
        )

    return create_error_response(
        status_code=exc.status_code,
        code=exc.error_code,
        message=exc.message,
        details=exc.details,
        trace_id=trace_id,
        headers=exc.headers,
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> Any:
    """Handle standard FastAPI/Starlette HTTPExceptions."""
    trace_id = _extract_trace_id(request)

    status_code_map: dict[int, str] = {
        400: "BAD_REQUEST",
        401: "AUTHENTICATION_REQUIRED",
        403: "PERMISSION_DENIED",
        404: "RESOURCE_NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        408: "REQUEST_TIMEOUT",
        409: "RESOURCE_CONFLICT",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_SERVER_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
        504: "GATEWAY_TIMEOUT",
    }

    code = status_code_map.get(exc.status_code, f"HTTP_{exc.status_code}")

    if isinstance(exc.detail, dict):
        message = exc.detail.get("message", "An HTTP error occurred.")
        details = exc.detail.get("details", exc.detail)
    else:
        message = str(exc.detail) if exc.detail else "An HTTP error occurred."
        details = {}

    logger.warning(
        "http_exception_handled",
        status_code=exc.status_code,
        code=code,
        message=message,
        path=str(request.url.path),
        method=request.method,
        trace_id=trace_id,
    )

    return create_error_response(
        status_code=exc.status_code,
        code=code,
        message=message,
        details=details,
        trace_id=trace_id,
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError | ValidationError
) -> Any:
    """Handle request payload, query, and path parameter validation failures."""
    trace_id = _extract_trace_id(request)

    formatted_errors: list[dict[str, Any]] = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error.get("loc", []))
        formatted_errors.append(
            {
                "field": field,
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "validation_error"),
            }
        )

    logger.warning(
        "request_validation_failed",
        error_count=len(formatted_errors),
        errors=formatted_errors,
        path=str(request.url.path),
        method=request.method,
        trace_id=trace_id,
    )

    return create_error_response(
        status_code=422,
        code="VALIDATION_ERROR",
        message="The requested operation failed request validation.",
        details={"validation_errors": formatted_errors},
        trace_id=trace_id,
    )


async def sqlalchemy_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> Any:
    """Handle database-level exceptions without leaking internal schemas or SQL statements."""
    trace_id = _extract_trace_id(request)

    logger.error(
        "database_exception_caught",
        error=str(exc),
        path=str(request.url.path),
        method=request.method,
        trace_id=trace_id,
        exc_info=True,
    )

    if isinstance(exc, IntegrityError):
        return create_error_response(
            status_code=409,
            code="RESOURCE_CONFLICT",
            message="A database integrity or unique constraint conflict occurred.",
            trace_id=trace_id,
        )

    return create_error_response(
        status_code=500,
        code="DATABASE_ERROR",
        message="A database error occurred while processing the request.",
        trace_id=trace_id,
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> Any:
    """Catch-all handler for unexpected internal server errors (500)."""
    trace_id = _extract_trace_id(request)

    logger.critical(
        "unhandled_exception_occurred",
        error_type=exc.__class__.__name__,
        error_message=str(exc),
        path=str(request.url.path),
        method=request.method,
        trace_id=trace_id,
        exc_info=True,
    )

    return create_error_response(
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected internal server error occurred. Please contact system support.",
        trace_id=trace_id,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all centralized exception handlers onto the FastAPI application instance."""
    app.add_exception_handler(BaseAppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
