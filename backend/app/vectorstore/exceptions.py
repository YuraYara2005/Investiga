"""Vector Store Exception Hierarchy.

Custom exceptions for vector database operations, collection management,
connection failures, dimensionality validation, and query execution.
"""

from __future__ import annotations

from typing import Any

from app.exceptions.base import BaseAppException


class VectorStoreException(BaseAppException):
    """Base exception for all vector database operations."""

    status_code: int = 500
    error_code: str = "VECTOR_STORE_ERROR"
    message: str = "An error occurred during vector database operations."


class VectorStoreConnectionException(VectorStoreException):
    """Raised when the vector database backend cannot be reached or health check fails."""

    status_code: int = 503
    error_code: str = "VECTOR_STORE_CONNECTION_FAILED"
    message: str = "Failed to establish or maintain connection to the vector database."

    def __init__(
        self,
        message: str | None = None,
        host: str | None = None,
        port: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        if host:
            merged_details["host"] = host
        if port:
            merged_details["port"] = port
        super().__init__(
            message=message or self.message,
            error_code=self.error_code,
            status_code=self.status_code,
            details=merged_details,
        )


class CollectionNotFoundException(VectorStoreException):
    """Raised when an operation targets a non-existent vector collection."""

    status_code: int = 404
    error_code: str = "VECTOR_COLLECTION_NOT_FOUND"
    message: str = "The specified vector collection does not exist."

    def __init__(
        self,
        collection_name: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        merged_details["collection_name"] = collection_name
        msg = message or f"Vector collection '{collection_name}' was not found."
        super().__init__(
            message=msg,
            error_code=self.error_code,
            status_code=self.status_code,
            details=merged_details,
        )


class CollectionAlreadyExistsException(VectorStoreException):
    """Raised when attempting to create a vector collection that already exists."""

    status_code: int = 409
    error_code: str = "VECTOR_COLLECTION_ALREADY_EXISTS"
    message: str = "The specified vector collection already exists."

    def __init__(
        self,
        collection_name: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        merged_details["collection_name"] = collection_name
        msg = message or f"Vector collection '{collection_name}' already exists."
        super().__init__(
            message=msg,
            error_code=self.error_code,
            status_code=self.status_code,
            details=merged_details,
        )


class VectorUpsertException(VectorStoreException):
    """Raised when vector insertion or update fails."""

    status_code: int = 500
    error_code: str = "VECTOR_UPSERT_FAILED"
    message: str = "Failed to upsert vector records into the vector database."

    def __init__(
        self,
        collection_name: str,
        record_count: int = 0,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        merged_details["collection_name"] = collection_name
        merged_details["record_count"] = record_count
        if reason:
            merged_details["reason"] = reason
        msg = f"Failed to upsert {record_count} vectors into collection '{collection_name}': {reason or 'Unknown error'}"
        super().__init__(
            message=msg,
            error_code=self.error_code,
            status_code=self.status_code,
            details=merged_details,
        )


class VectorQueryException(VectorStoreException):
    """Raised when vector search or retrieval operation fails."""

    status_code: int = 500
    error_code: str = "VECTOR_QUERY_FAILED"
    message: str = "Failed to execute vector search or retrieval query."

    def __init__(
        self,
        collection_name: str,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        merged_details["collection_name"] = collection_name
        if reason:
            merged_details["reason"] = reason
        msg = f"Vector query on collection '{collection_name}' failed: {reason or 'Unknown error'}"
        super().__init__(
            message=msg,
            error_code=self.error_code,
            status_code=self.status_code,
            details=merged_details,
        )


class VectorDimensionMismatchException(VectorStoreException):
    """Raised when a vector dimension does not match the collection configuration."""

    status_code: int = 422
    error_code: str = "VECTOR_DIMENSION_MISMATCH"
    message: str = "Vector dimension does not match collection configuration."

    def __init__(
        self,
        expected_dim: int,
        actual_dim: int,
        collection_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        merged_details["expected_dimension"] = expected_dim
        merged_details["actual_dimension"] = actual_dim
        if collection_name:
            merged_details["collection_name"] = collection_name
        msg = (
            f"Vector dimension mismatch: expected {expected_dim}, "
            f"received {actual_dim}"
            + (f" for collection '{collection_name}'" if collection_name else "")
        )
        super().__init__(
            message=msg,
            error_code=self.error_code,
            status_code=self.status_code,
            details=merged_details,
        )


class VectorDeleteException(VectorStoreException):
    """Raised when vector deletion fails."""

    status_code: int = 500
    error_code: str = "VECTOR_DELETE_FAILED"
    message: str = "Failed to delete vector points from the collection."

    def __init__(
        self,
        collection_name: str,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        merged_details["collection_name"] = collection_name
        if reason:
            merged_details["reason"] = reason
        msg = f"Failed to delete vectors from '{collection_name}': {reason or 'Unknown error'}"
        super().__init__(
            message=msg,
            error_code=self.error_code,
            status_code=self.status_code,
            details=merged_details,
        )


class InvalidFilterException(VectorStoreException):
    """Raised when a metadata filter specification is malformed or invalid."""

    status_code: int = 422
    error_code: str = "INVALID_VECTOR_FILTER"
    message: str = "The provided metadata filter specification is invalid."
