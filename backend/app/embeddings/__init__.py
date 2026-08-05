"""Embedding Subsystem for Investiga.

Provides enterprise-grade embedding generation with provider abstraction,
thread-safe model loading, batch processing, and async support.
"""

from app.embeddings.batching import (
    compute_adaptive_batch_size,
    iter_batches,
    iter_batches_with_indices,
    validate_texts,
)
from app.embeddings.embedding_service import EmbeddingService, create_embedding_service
from app.embeddings.exceptions import (
    EmbeddingDimensionMismatchException,
    EmbeddingException,
    EmbeddingInferenceException,
    EmbeddingModelLoadException,
    EmbeddingProviderNotConfiguredException,
    EmptyEmbeddingInputException,
)
from app.embeddings.models import (
    BatchEmbeddingResult,
    EmbeddingModelInfo,
    EmbeddingVector,
)
from app.embeddings.provider import EmbeddingProvider
from app.embeddings.sentence_transformer_provider import SentenceTransformerProvider

__all__ = [
    "BatchEmbeddingResult",
    "EmbeddingDimensionMismatchException",
    "EmbeddingException",
    "EmbeddingInferenceException",
    "EmbeddingModelInfo",
    "EmbeddingModelLoadException",
    "EmbeddingProvider",
    "EmbeddingProviderNotConfiguredException",
    "EmbeddingService",
    "EmbeddingVector",
    "EmptyEmbeddingInputException",
    "SentenceTransformerProvider",
    "compute_adaptive_batch_size",
    "create_embedding_service",
    "iter_batches",
    "iter_batches_with_indices",
    "validate_texts",
]
