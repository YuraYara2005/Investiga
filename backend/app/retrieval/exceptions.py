"""Retrieval Engine Exception Hierarchy.

Defines standardized domain exceptions for query validation, dense search failures,
sparse BM25 failures, fusion errors, strategy routing, and timeout conditions.
"""

from __future__ import annotations

from typing import Any

from app.exceptions.base import BaseAppException


class RetrievalException(BaseAppException):
    """Base exception for all retrieval and search pipeline errors."""

    status_code = 500
    error_code = "RETRIEVAL_ERROR"
    message = "An error occurred while executing the retrieval pipeline."


class InvalidQueryException(RetrievalException):
    """Raised when a user query fails validation (empty, too long, malformed)."""

    status_code = 400
    error_code = "INVALID_SEARCH_QUERY"

    def __init__(
        self,
        reason: str,
        query_text: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        if query_text is not None:
            merged_details["query_preview"] = (
                query_text[:100] + "..." if len(query_text) > 100 else query_text
            )
        merged_details["reason"] = reason
        super().__init__(
            message=f"Invalid search query: {reason}",
            error_code=self.error_code,
            status_code=self.status_code,
            details=merged_details,
        )


class DenseRetrievalException(RetrievalException):
    """Raised when dense vector search or embedding generation fails."""

    status_code = 500
    error_code = "DENSE_RETRIEVAL_ERROR"

    def __init__(
        self,
        reason: str,
        collection_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        merged_details["reason"] = reason
        if collection_name:
            merged_details["collection_name"] = collection_name
        super().__init__(
            message=f"Dense vector retrieval failed: {reason}",
            error_code=self.error_code,
            status_code=self.status_code,
            details=merged_details,
        )


class SparseRetrievalException(RetrievalException):
    """Raised when BM25 keyword search or inverted index lookup fails."""

    status_code = 500
    error_code = "SPARSE_RETRIEVAL_ERROR"

    def __init__(
        self,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        merged_details["reason"] = reason
        super().__init__(
            message=f"Sparse BM25 retrieval failed: {reason}",
            error_code=self.error_code,
            status_code=self.status_code,
            details=merged_details,
        )


class FusionException(RetrievalException):
    """Raised when rank fusion or score normalization fails."""

    status_code = 500
    error_code = "FUSION_ERROR"

    def __init__(
        self,
        strategy_name: str,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        merged_details["strategy_name"] = strategy_name
        merged_details["reason"] = reason
        super().__init__(
            message=f"Rank fusion strategy '{strategy_name}' failed: {reason}",
            error_code=self.error_code,
            status_code=self.status_code,
            details=merged_details,
        )


class StrategyNotFoundException(RetrievalException):
    """Raised when a requested retrieval strategy is not registered."""

    status_code = 400
    error_code = "STRATEGY_NOT_FOUND"

    def __init__(self, strategy_name: str) -> None:
        super().__init__(
            message=f"Retrieval strategy '{strategy_name}' is not registered.",
            error_code=self.error_code,
            status_code=self.status_code,
            details={"strategy_name": strategy_name},
        )


class FusionStrategyNotFoundException(RetrievalException):
    """Raised when a requested fusion strategy is not registered."""

    status_code = 400
    error_code = "FUSION_STRATEGY_NOT_FOUND"

    def __init__(self, fusion_name: str) -> None:
        super().__init__(
            message=f"Fusion strategy '{fusion_name}' is not registered.",
            error_code=self.error_code,
            status_code=self.status_code,
            details={"fusion_name": fusion_name},
        )


class RetrievalTimeoutException(RetrievalException):
    """Raised when retrieval exceeds the configured timeout threshold."""

    status_code = 504
    error_code = "RETRIEVAL_TIMEOUT"

    def __init__(self, timeout_seconds: float) -> None:
        super().__init__(
            message=f"Retrieval operation timed out after {timeout_seconds:.2f} seconds.",
            error_code=self.error_code,
            status_code=self.status_code,
            details={"timeout_seconds": timeout_seconds},
        )


class RetrievalCancelledException(RetrievalException):
    """Raised when retrieval operation is cancelled by the caller."""

    status_code = 499
    error_code = "RETRIEVAL_CANCELLED"

    def __init__(self) -> None:
        super().__init__(
            message="Retrieval request was cancelled.",
            error_code=self.error_code,
            status_code=self.status_code,
        )
