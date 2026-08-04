"""Domain Exception Hierarchy for Investiga.

This module defines specialized domain and business exceptions. Future business
domains (Authentication, Investigation, Knowledge Base, Retrieval, Analytics)
inherit from these classes to represent domain rule violations cleanly.
"""

from typing import Any
from app.exceptions.base import BaseAppException


class DomainException(BaseAppException):
    """Raised when an operation violates an explicit domain invariant or business rule."""

    status_code: int = 400
    error_code: str = "DOMAIN_RULE_VIOLATION"
    message: str = "A domain business rule was violated."


class NotFoundException(BaseAppException):
    """Raised when a requested resource or entity does not exist."""

    status_code: int = 404
    error_code: str = "RESOURCE_NOT_FOUND"
    message: str = "The requested resource was not found."

    def __init__(
        self,
        resource_name: str | None = None,
        identifier: Any = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if message is None and resource_name:
            if identifier is not None:
                message = f"{resource_name} with identifier '{identifier}' was not found."
            else:
                message = f"{resource_name} was not found."
        super().__init__(
            message=message or self.message,
            error_code=self.error_code,
            status_code=self.status_code,
            details=details,
        )


class ConflictException(BaseAppException):
    """Raised when an entity mutation causes a duplicate key or state collision."""

    status_code: int = 409
    error_code: str = "RESOURCE_CONFLICT"
    message: str = "A conflicting resource already exists or the entity is in a conflicting state."


class ValidationException(BaseAppException):
    """Raised when custom business validation fails on input data."""

    status_code: int = 422
    error_code: str = "VALIDATION_ERROR"
    message: str = "The supplied input failed semantic validation."


class UnauthorizedException(BaseAppException):
    """Raised when an unauthenticated client attempts to access a protected resource."""

    status_code: int = 401
    error_code: str = "AUTHENTICATION_REQUIRED"
    message: str = "Authentication credentials are required or invalid."

    def __init__(
        self,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        default_headers = {"WWW-Authenticate": "Bearer"}
        if headers:
            default_headers.update(headers)
        super().__init__(
            message=message or self.message,
            error_code=self.error_code,
            status_code=self.status_code,
            details=details,
            headers=default_headers,
        )


class ForbiddenException(BaseAppException):
    """Raised when an authenticated client lacks the permissions required for an action."""

    status_code: int = 403
    error_code: str = "PERMISSION_DENIED"
    message: str = "You do not have the required permissions to perform this action."


class RateLimitExceededException(BaseAppException):
    """Raised when a client exceeds API rate quotas."""

    status_code: int = 429
    error_code: str = "RATE_LIMIT_EXCEEDED"
    message: str = "API request rate limit exceeded. Please retry later."

    def __init__(
        self,
        retry_after_seconds: int = 60,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        custom_details = {"retry_after_seconds": retry_after_seconds}
        if details:
            custom_details.update(details)
        headers = {"Retry-After": str(retry_after_seconds)}
        super().__init__(
            message=message or self.message,
            error_code=self.error_code,
            status_code=self.status_code,
            details=custom_details,
            headers=headers,
        )


class ServiceUnavailableException(BaseAppException):
    """Raised when an external downstream dependency or subsystem is temporarily unreachable."""

    status_code: int = 503
    error_code: str = "SERVICE_UNAVAILABLE"
    message: str = "A required platform service is temporarily unavailable."


class DatabaseException(BaseAppException):
    """Raised when an unrecoverable database or persistence failure occurs."""

    status_code: int = 500
    error_code: str = "DATABASE_ERROR"
    message: str = "A database operation encountered an unrecoverable error."
