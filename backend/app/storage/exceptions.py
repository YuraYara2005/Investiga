"""Storage Domain and Validation Exceptions.

This module defines specialized exceptions for file storage operations,
upload security constraints, size violations, and content type validations.
"""

from typing import Any

from app.exceptions.domain import (
    DomainException,
    NotFoundException,
    ValidationException,
)


class StorageException(DomainException):
    """Base exception for file storage system operations."""

    error_code: str = "STORAGE_ERROR"
    message: str = "A file storage operation failed."


class InvalidFileException(ValidationException):
    """Raised when an uploaded file fails security, naming, or structural validations."""

    error_code: str = "INVALID_FILE"
    message: str = "The uploaded file is invalid or contains suspicious attributes."


class FileTooLargeException(ValidationException):
    """Raised when an uploaded file exceeds the configured maximum byte size."""

    error_code: str = "FILE_TOO_LARGE"
    message: str = "The uploaded file exceeds the maximum permitted size limit."

    def __init__(
        self,
        size_bytes: int,
        max_size_mb: int,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        custom_details = {
            "size_bytes": size_bytes,
            "max_size_mb": max_size_mb,
            "max_size_bytes": max_size_mb * 1024 * 1024,
        }
        if details:
            custom_details.update(details)
        super().__init__(
            message=message
            or f"File size of {size_bytes} bytes exceeds maximum allowed limit of {max_size_mb} MB.",
            details=custom_details,
        )


class UnsupportedFileTypeException(ValidationException):
    """Raised when a file extension or MIME content type is prohibited."""

    error_code: str = "UNSUPPORTED_FILE_TYPE"
    message: str = "The file type or MIME format is not permitted for ingestion."


class StorageFileNotFoundException(NotFoundException):
    """Raised when a referenced file does not exist in the physical storage provider."""

    error_code: str = "STORAGE_FILE_NOT_FOUND"
    message: str = "The requested file does not exist in the storage system."
