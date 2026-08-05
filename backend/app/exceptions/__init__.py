"""Exceptions package initialization for Investiga.

Provides root and specialized domain exceptions, error response models, and
centralized FastAPI exception registration handlers.
"""

from app.exceptions.base import BaseAppException
from app.exceptions.domain import (
    ConflictException,
    DatabaseException,
    DomainException,
    ForbiddenException,
    NotFoundException,
    RateLimitExceededException,
    ServiceUnavailableException,
    UnauthorizedException,
    ValidationException,
)
from app.exceptions.handlers import register_exception_handlers
from app.exceptions.responses import (
    ErrorDetail,
    ErrorResponse,
    create_error_response,
)

__all__ = [
    "BaseAppException",
    "ConflictException",
    "DatabaseException",
    "DomainException",
    "ErrorDetail",
    "ErrorResponse",
    "ForbiddenException",
    "NotFoundException",
    "RateLimitExceededException",
    "ServiceUnavailableException",
    "UnauthorizedException",
    "ValidationException",
    "create_error_response",
    "register_exception_handlers",
]
