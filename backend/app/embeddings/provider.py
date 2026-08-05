"""Embedding Provider Interface.

Defines the abstract contract that all embedding model backends must implement.
No model-specific code should appear outside a concrete Provider implementation.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

import numpy as np

from app.embeddings.models import EmbeddingModelInfo


class EmbeddingProvider(ABC):
    """Abstract base class for all embedding model providers.

    Every concrete embedding backend (SentenceTransformer, OpenAI, Cohere, etc.)
    must implement this interface. The embedding service depends only on this ABC.
    """

    @property
    @abstractmethod
    def model_info(self) -> EmbeddingModelInfo:
        """Return metadata about the loaded model.

        Returns:
            EmbeddingModelInfo: Dimension, device, max_seq_length, etc.
        """
        ...

    @property
    def dimension(self) -> int:
        """Shortcut for the model output embedding dimension."""
        return self.model_info.dimension

    @property
    def model_name(self) -> str:
        """Shortcut for the model identifier."""
        return self.model_info.model_name

    @abstractmethod
    def encode_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
        normalize: bool = True,
        show_progress: bool = False,
    ) -> np.ndarray:
        """Synchronously encode a list of texts into embedding vectors.

        Args:
            texts: Non-empty list of text strings to embed.
            batch_size: Number of texts to process per model forward pass.
            normalize: If True, L2-normalize each output vector.
            show_progress: If True, show tqdm progress bars.

        Returns:
            np.ndarray: Shape (len(texts), dimension), dtype float32.
        """
        ...

    def encode_single(
        self,
        text: str,
        normalize: bool = True,
    ) -> np.ndarray:
        """Encode a single text string into an embedding vector.

        Default implementation delegates to encode_batch. Override if single
        inference has a faster code path.

        Args:
            text: Input text string.
            normalize: If True, L2-normalize the output vector.

        Returns:
            np.ndarray: Shape (dimension,), dtype float32.
        """
        result = self.encode_batch([text], batch_size=1, normalize=normalize)
        return result[0]

    async def encode_batch_async(
        self,
        texts: list[str],
        batch_size: int = 32,
        normalize: bool = True,
    ) -> np.ndarray:
        """Asynchronously encode a batch of texts via threadpool offload.

        Args:
            texts: Non-empty list of text strings.
            batch_size: Per-batch size for inference.
            normalize: If True, L2-normalize each output vector.

        Returns:
            np.ndarray: Shape (len(texts), dimension), dtype float32.
        """
        return await asyncio.to_thread(
            self.encode_batch,
            texts,
            batch_size,
            normalize,
            False,
        )

    async def encode_single_async(
        self,
        text: str,
        normalize: bool = True,
    ) -> np.ndarray:
        """Asynchronously encode a single text string.

        Args:
            text: Input text string.
            normalize: If True, L2-normalize the output vector.

        Returns:
            np.ndarray: Shape (dimension,), dtype float32.
        """
        return await asyncio.to_thread(self.encode_single, text, normalize)

    @staticmethod
    def normalize_vectors(vectors: np.ndarray) -> np.ndarray:
        """L2-normalize a batch of vectors in-place and return them.

        Zero-norm vectors are left as-is to avoid division by zero.

        Args:
            vectors: Shape (N, D) float32 array.

        Returns:
            np.ndarray: L2-normalized vectors of the same shape.
        """
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        # Avoid division by zero for zero-length vectors
        norms = np.where(norms == 0.0, 1.0, norms)
        return (vectors / norms).astype(np.float32)
