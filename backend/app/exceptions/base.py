"""Base Application Exception Hierarchy for Investiga.

This module defines the root exception class from which all domain, business,
and infrastructure exceptions must inherit.
"""

from typing import Any


class BaseAppException(Exception):
    """Root application exception for Investiga.

    All custom domain, service, and infrastructure exceptions inherit from this base.
    Exception handlers inspect these attributes to automatically build standardized
    JSON API error responses.

    Attributes:
        status_code: Corresponding HTTP status code.
        error_code: Unique machine-readable error string (e.g. 'RESOURCE_NOT_FOUND').
        message: Human-readable error explanation.
        details: Optional structured dictionary containing field-level or context data.
        headers: Optional HTTP headers to include in the response (e.g. 'Retry-After').
    """

    status_code: int = 500
    error_code: str = "INTERNAL_SERVER_ERROR"
    message: str = "An unexpected error occurred within the application."

    def __init__(
        self,
        message: str | None = None,
        error_code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        if message is not None:
            self.message = message
        if error_code is not None:
            self.error_code = error_code
        if status_code is not None:
            self.status_code = status_code
        self.details: dict[str, Any] = details or {}
        self.headers: dict[str, str] | None = headers
        super().__init__(self.message)

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} status_code={self.status_code} "
            f"error_code='{self.error_code}' message='{self.message}'>"
        )
