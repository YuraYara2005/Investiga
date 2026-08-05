"""Embedding Subsystem Exceptions.

Defines the exception hierarchy for all embedding-related failures.
"""

from __future__ import annotations

from typing import Any

from app.exceptions.base import BaseAppException


class EmbeddingException(BaseAppException):
    """Base exception for all embedding subsystem errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "EMBEDDING_FAILED",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            details=details or {},
        )


class EmbeddingModelLoadException(EmbeddingException):
    """Raised when an embedding model fails to load from disk or HuggingFace Hub."""

    def __init__(self, model_name: str, reason: str) -> None:
        super().__init__(
            message=f"Failed to load embedding model '{model_name}': {reason}",
            error_code="EMBEDDING_MODEL_LOAD_FAILED",
            details={"model_name": model_name, "reason": reason},
        )


class EmbeddingInferenceException(EmbeddingException):
    """Raised when embedding inference fails during encode."""

    def __init__(self, reason: str, model_name: str | None = None) -> None:
        super().__init__(
            message=f"Embedding inference failed: {reason}",
            error_code="EMBEDDING_INFERENCE_FAILED",
            details={"reason": reason, "model_name": model_name},
        )


class EmptyEmbeddingInputException(EmbeddingException):
    """Raised when an empty or blank text list is passed for embedding."""

    def __init__(self) -> None:
        super().__init__(
            message="Cannot embed empty or whitespace-only text input.",
            error_code="EMPTY_EMBEDDING_INPUT",
            status_code=422,
        )


class EmbeddingDimensionMismatchException(EmbeddingException):
    """Raised when the output embedding dimension differs from the expected dimension."""

    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(
            message=f"Embedding dimension mismatch: expected {expected}, got {actual}.",
            error_code="EMBEDDING_DIMENSION_MISMATCH",
            details={"expected": expected, "actual": actual},
        )


class EmbeddingProviderNotConfiguredException(EmbeddingException):
    """Raised when an embedding provider is used before configuration is complete."""

    def __init__(self, provider_name: str) -> None:
        super().__init__(
            message=f"Embedding provider '{provider_name}' is not properly configured.",
            error_code="EMBEDDING_PROVIDER_NOT_CONFIGURED",
            details={"provider_name": provider_name},
        )
