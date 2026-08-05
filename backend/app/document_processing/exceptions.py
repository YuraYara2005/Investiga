"""Domain Exceptions for Document Processing Subsystem.

Defines granular, schema-compliant exceptions for parsing failures,
unsupported MIME formats, corrupt binaries, and empty documents.
"""

from typing import Any

from app.exceptions.base import BaseAppException


class DocumentProcessingException(BaseAppException):
    """Base exception for all document parsing, transformation, and extraction errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "DOCUMENT_PROCESSING_FAILED",
        status_code: int = 422,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            details=details or {},
        )


class UnsupportedDocumentException(DocumentProcessingException):
    """Raised when an uploaded document format has no registered parser."""

    def __init__(
        self,
        extension: str,
        mime_type: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        merged_details.update({"extension": extension, "mime_type": mime_type})
        super().__init__(
            message=f"Unsupported document format '{extension}' (MIME: {mime_type or 'unknown'}).",
            error_code="UNSUPPORTED_DOCUMENT_FORMAT",
            status_code=422,
            details=merged_details,
        )


class CorruptedDocumentException(DocumentProcessingException):
    """Raised when document payload fails parsing due to structure corruption or invalid headers."""

    def __init__(
        self,
        filename: str,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        merged_details.update({"filename": filename, "reason": reason})
        super().__init__(
            message=f"Document '{filename}' is corrupted or unreadable: {reason}",
            error_code="CORRUPTED_DOCUMENT",
            status_code=422,
            details=merged_details,
        )


class EmptyDocumentException(DocumentProcessingException):
    """Raised when document payload contains zero extractable text or content."""

    def __init__(
        self,
        filename: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        merged_details.update({"filename": filename})
        super().__init__(
            message=f"Document '{filename}' contains no extractable text.",
            error_code="EMPTY_DOCUMENT",
            status_code=422,
            details=merged_details,
        )
