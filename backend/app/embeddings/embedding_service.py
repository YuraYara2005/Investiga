"""Embedding Service.

High-level orchestration layer that unifies provider access, batch processing,
latency measurement, structured logging, and result assembly into EmbeddingVector
and BatchEmbeddingResult domain objects.

This is the only class that consumers (API endpoints, pipelines) should depend on.
The concrete provider is injected at construction time via DI.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import numpy as np

from app.core.logging import get_logger
from app.embeddings.batching import (
    compute_adaptive_batch_size,
    validate_texts,
)
from app.embeddings.exceptions import EmptyEmbeddingInputException
from app.embeddings.models import (
    BatchEmbeddingResult,
    EmbeddingModelInfo,
    EmbeddingVector,
)
from app.embeddings.provider import EmbeddingProvider

logger = get_logger(__name__)


class EmbeddingService:
    """High-level embedding orchestration service.

    Wraps an EmbeddingProvider with batching, latency metrics, input validation,
    structured logging, and result assembly. Suitable for direct FastAPI DI.

    Example:
        provider = SentenceTransformerProvider(model_name="BAAI/bge-base-en-v1.5")
        service = EmbeddingService(provider=provider)
        result = await service.embed_texts(["text one", "text two"])
    """

    def __init__(
        self,
        provider: EmbeddingProvider,
        default_batch_size: int = 32,
        adaptive_batching: bool = True,
        normalize: bool = True,
    ) -> None:
        """Initialize the embedding service with a concrete provider.

        Args:
            provider: Any EmbeddingProvider implementation.
            default_batch_size: Default batch size; ignored when adaptive_batching=True.
            adaptive_batching: Automatically compute batch size from text lengths.
            normalize: Whether to L2-normalize output vectors.
        """
        self._provider = provider
        self._default_batch_size = default_batch_size
        self._adaptive_batching = adaptive_batching
        self._normalize = normalize

    @property
    def model_info(self) -> EmbeddingModelInfo:
        """Delegate model metadata to the underlying provider."""
        return self._provider.model_info

    @property
    def dimension(self) -> int:
        """Embedding dimension shortcut."""
        return self._provider.dimension

    # ------------------------------------------------------------------
    # Synchronous API
    # ------------------------------------------------------------------

    def embed_text(
        self,
        text: str,
        text_id: str | None = None,
    ) -> EmbeddingVector:
        """Synchronously embed a single text string.

        Args:
            text: Input text to embed.
            text_id: Optional identifier for this text.

        Returns:
            EmbeddingVector: Populated embedding vector.

        Raises:
            EmptyEmbeddingInputException: If text is blank.
        """
        stripped = text.strip()
        if not stripped:
            raise EmptyEmbeddingInputException()

        start_time = time.perf_counter()
        vector_array: np.ndarray = self._provider.encode_single(
            stripped, normalize=self._normalize
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        logger.debug(
            "embedding_single_text",
            model_name=self._provider.model_name,
            latency_ms=round(elapsed_ms, 2),
        )

        return EmbeddingVector(
            text_id=text_id or str(uuid.uuid4()),
            text=stripped,
            vector=vector_array.tolist(),
            dimension=len(vector_array),
            model_name=self._provider.model_name,
            is_normalized=self._normalize,
        )

    def embed_texts(
        self,
        texts: list[str],
        text_ids: list[str] | None = None,
        batch_size: int | None = None,
    ) -> BatchEmbeddingResult:
        """Synchronously embed a batch of text strings.

        Args:
            texts: List of text strings to embed.
            text_ids: Optional list of identifiers (must match len(texts) if provided).
            batch_size: Override per-batch size. Uses adaptive batching if None.

        Returns:
            BatchEmbeddingResult: Aggregate result with all embedding vectors.

        Raises:
            EmptyEmbeddingInputException: If all texts are blank.
        """
        validated = validate_texts(texts)
        resolved_batch_size = self._resolve_batch_size(validated, batch_size)

        start_time = time.perf_counter()
        vector_matrix: np.ndarray = self._provider.encode_batch(
            validated,
            batch_size=resolved_batch_size,
            normalize=self._normalize,
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        throughput = (len(validated) / elapsed_ms * 1000.0) if elapsed_ms > 0 else 0.0

        embedding_vectors = self._assemble_vectors(validated, vector_matrix, text_ids)

        logger.info(
            "embedding_batch_complete",
            model_name=self._provider.model_name,
            total_texts=len(validated),
            batch_size=resolved_batch_size,
            latency_ms=round(elapsed_ms, 2),
            throughput_per_sec=round(throughput, 2),
        )

        return BatchEmbeddingResult(
            embeddings=embedding_vectors,
            total_texts=len(validated),
            successful_embeddings=len(embedding_vectors),
            model_name=self._provider.model_name,
            dimension=self._provider.dimension,
            latency_ms=round(elapsed_ms, 2),
            throughput_texts_per_sec=round(throughput, 2),
            metadata={"batch_size_used": resolved_batch_size},
        )

    # ------------------------------------------------------------------
    # Async API
    # ------------------------------------------------------------------

    async def embed_text_async(
        self,
        text: str,
        text_id: str | None = None,
    ) -> EmbeddingVector:
        """Asynchronously embed a single text string.

        Args:
            text: Input text to embed.
            text_id: Optional identifier.

        Returns:
            EmbeddingVector: Populated embedding vector.
        """
        import asyncio

        return await asyncio.to_thread(self.embed_text, text, text_id)

    async def embed_texts_async(
        self,
        texts: list[str],
        text_ids: list[str] | None = None,
        batch_size: int | None = None,
    ) -> BatchEmbeddingResult:
        """Asynchronously embed a batch of texts.

        Args:
            texts: List of text strings to embed.
            text_ids: Optional list of identifiers.
            batch_size: Optional per-batch size override.

        Returns:
            BatchEmbeddingResult: Complete batch embedding result.
        """
        import asyncio

        return await asyncio.to_thread(self.embed_texts, texts, text_ids, batch_size)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_batch_size(
        self,
        texts: list[str],
        override: int | None,
    ) -> int:
        """Resolve the effective batch size for a list of texts."""
        if override is not None and override > 0:
            return override
        if self._adaptive_batching:
            return compute_adaptive_batch_size(
                text_lengths=[len(t) for t in texts],
                max_batch_size=self._default_batch_size,
            )
        return self._default_batch_size

    def _assemble_vectors(
        self,
        texts: list[str],
        matrix: np.ndarray,
        text_ids: list[str] | None,
    ) -> list[EmbeddingVector]:
        """Convert a numpy embedding matrix into a list of EmbeddingVector objects."""
        vectors: list[EmbeddingVector] = []
        for i, (text, row) in enumerate(zip(texts, matrix, strict=True)):
            tid = text_ids[i] if text_ids and i < len(text_ids) else str(uuid.uuid4())
            vectors.append(
                EmbeddingVector(
                    text_id=tid,
                    text=text,
                    vector=row.tolist(),
                    dimension=len(row),
                    model_name=self._provider.model_name,
                    is_normalized=self._normalize,
                )
            )
        return vectors


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def create_embedding_service(
    model_name: str | None = None,
    device: str | None = None,
    normalize: bool = True,
    batch_size: int = 32,
    adaptive_batching: bool = True,
    cache_folder: str | None = None,
    trust_remote_code: bool = False,
    extra_model_kwargs: dict[str, Any] | None = None,
    auto_load: bool = True,
) -> EmbeddingService:
    """Factory: create and return a configured EmbeddingService.

    Reads the model name from Settings if not provided explicitly.

    Args:
        model_name: HuggingFace model ID. Falls back to Settings.embeddings.model_name.
        device: Compute device override. Auto-detected if None.
        normalize: Whether to L2-normalize output vectors.
        batch_size: Default inference batch size.
        adaptive_batching: Enable adaptive batch size computation.
        cache_folder: HuggingFace Hub cache directory override.
        trust_remote_code: Trust remote model code (for certain models).
        extra_model_kwargs: Additional kwargs forwarded to SentenceTransformer.
        auto_load: If True, call provider.load() before returning.

    Returns:
        EmbeddingService: Ready-to-use service instance.
    """
    from app.core.config import get_settings
    from app.embeddings.sentence_transformer_provider import SentenceTransformerProvider

    settings = get_settings()
    embedding_cfg = settings.embeddings

    resolved_model = model_name or embedding_cfg.model_name
    resolved_batch_size = batch_size or embedding_cfg.batch_size
    resolved_normalize = (
        normalize if normalize is not None else embedding_cfg.normalize_embeddings
    )

    provider = SentenceTransformerProvider(
        model_name=resolved_model,
        device=device or embedding_cfg.device or None,
        normalize_embeddings=resolved_normalize,
        cache_folder=cache_folder or embedding_cfg.cache_folder or None,
        trust_remote_code=trust_remote_code,
        model_kwargs=extra_model_kwargs,
    )

    if auto_load:
        provider.load()

    return EmbeddingService(
        provider=provider,
        default_batch_size=resolved_batch_size,
        adaptive_batching=adaptive_batching,
        normalize=resolved_normalize,
    )
