"""Exception Hierarchy for the Document Ingestion Subsystem.

Provides structured, clean domain exceptions capturing failure context, stage,
and document identifier without leaking internal stack traces or database internals.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.exceptions.base import BaseAppException


class IngestionPipelineException(BaseAppException):
    """Base exception for all document ingestion pipeline failures."""

    error_code: str = "INGESTION_PIPELINE_ERROR"
    status_code: int = 500

    def __init__(
        self,
        message: str,
        document_id: uuid.UUID | str | None = None,
        stage: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        if document_id:
            merged_details["document_id"] = str(document_id)
        if stage:
            merged_details["stage"] = stage

        super().__init__(
            message=message,
            error_code=self.error_code,
            status_code=self.status_code,
            details=merged_details,
        )
        self.document_id = document_id
        self.stage = stage


class DocumentNotFoundException(IngestionPipelineException):
    """Raised when the specified document ID does not exist in the database."""

    error_code: str = "DOCUMENT_NOT_FOUND"
    status_code: int = 404

    def __init__(self, document_id: uuid.UUID | str) -> None:
        super().__init__(
            message=f"Knowledge document with ID '{document_id}' was not found.",
            document_id=document_id,
            stage="retrieval",
            details={"document_id": str(document_id)},
        )


class DocumentAlreadyProcessingException(IngestionPipelineException):
    """Raised when an ingestion job is requested for a document already in PROCESSING status."""

    error_code: str = "DOCUMENT_ALREADY_PROCESSING"
    status_code: int = 409

    def __init__(self, document_id: uuid.UUID | str) -> None:
        super().__init__(
            message=f"Document '{document_id}' is currently being processed by another worker.",
            document_id=document_id,
            stage="concurrency_check",
            details={"document_id": str(document_id)},
        )


class DocumentNotEligibleException(IngestionPipelineException):
    """Raised when a document is in an invalid state for ingestion."""

    error_code: str = "DOCUMENT_NOT_ELIGIBLE"
    status_code: int = 400

    def __init__(
        self, document_id: uuid.UUID | str, current_status: str, reason: str
    ) -> None:
        super().__init__(
            message=f"Document '{document_id}' is not eligible for ingestion (status={current_status}): {reason}",
            document_id=document_id,
            stage="validation",
            details={
                "document_id": str(document_id),
                "status": current_status,
                "reason": reason,
            },
        )


class StorageReadException(IngestionPipelineException):
    """Raised when the raw document binary cannot be retrieved from storage."""

    error_code: str = "STORAGE_READ_ERROR"
    status_code: int = 502

    def __init__(
        self, document_id: uuid.UUID | str, storage_path: str, reason: str
    ) -> None:
        super().__init__(
            message=f"Failed to read document binary from storage '{storage_path}': {reason}",
            document_id=document_id,
            stage="storage_read",
            details={"storage_path": storage_path, "reason": reason},
        )


class DocumentParsingStageException(IngestionPipelineException):
    """Raised when document parsing or extraction fails."""

    error_code: str = "DOCUMENT_PARSING_FAILED"
    status_code: int = 422

    def __init__(
        self, document_id: uuid.UUID | str, filename: str, reason: str
    ) -> None:
        super().__init__(
            message=f"Document parsing failed for '{filename}': {reason}",
            document_id=document_id,
            stage="parsing",
            details={"filename": filename, "reason": reason},
        )


class DocumentChunkingStageException(IngestionPipelineException):
    """Raised when text partitioning / chunking fails."""

    error_code: str = "DOCUMENT_CHUNKING_FAILED"
    status_code: int = 422

    def __init__(
        self, document_id: uuid.UUID | str, strategy: str, reason: str
    ) -> None:
        super().__init__(
            message=f"Document chunking failed with strategy '{strategy}': {reason}",
            document_id=document_id,
            stage="chunking",
            details={"strategy": strategy, "reason": reason},
        )


class EmbeddingStageException(IngestionPipelineException):
    """Raised when embedding generation inference fails."""

    error_code: str = "EMBEDDING_GENERATION_FAILED"
    status_code: int = 502

    def __init__(
        self, document_id: uuid.UUID | str, model_name: str, reason: str
    ) -> None:
        super().__init__(
            message=f"Embedding generation failed with model '{model_name}': {reason}",
            document_id=document_id,
            stage="embedding",
            details={"model_name": model_name, "reason": reason},
        )


class VectorIndexingStageException(IngestionPipelineException):
    """Raised when persisting vector points into Qdrant fails."""

    error_code: str = "VECTOR_INDEXING_FAILED"
    status_code: int = 502

    def __init__(
        self, document_id: uuid.UUID | str, collection_name: str, reason: str
    ) -> None:
        super().__init__(
            message=f"Vector indexing failed for collection '{collection_name}': {reason}",
            document_id=document_id,
            stage="vector_indexing",
            details={"collection_name": collection_name, "reason": reason},
        )


class DatabasePersistenceStageException(IngestionPipelineException):
    """Raised when persisting relational chunks or updating document state fails."""

    error_code: str = "DATABASE_PERSISTENCE_FAILED"
    status_code: int = 500

    def __init__(self, document_id: uuid.UUID | str, reason: str) -> None:
        super().__init__(
            message=f"Database persistence failed for document '{document_id}': {reason}",
            document_id=document_id,
            stage="database_persistence",
            details={"reason": reason},
        )
