"""Chunking Exceptions.

Defines all domain-specific errors raised by the chunking subsystem.
"""

from typing import Any

from app.exceptions.base import BaseAppException


class ChunkingException(BaseAppException):
    """Base exception for all chunking errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "CHUNKING_FAILED",
        status_code: int = 422,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            details=details or {},
        )


class EmptyTextException(ChunkingException):
    """Raised when document text is empty or whitespace-only."""

    def __init__(self, document_id: str | None = None) -> None:
        super().__init__(
            message="Cannot chunk empty or whitespace-only document text.",
            error_code="EMPTY_DOCUMENT_TEXT",
            details={"document_id": document_id},
        )


class InvalidChunkConfigException(ChunkingException):
    """Raised when chunk_size or overlap values are logically invalid."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            message=f"Invalid chunking configuration: {reason}",
            error_code="INVALID_CHUNK_CONFIG",
            details={"reason": reason},
        )
