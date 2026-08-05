"""SentenceTransformer Embedding Provider.

Concrete implementation of EmbeddingProvider using the sentence-transformers
library. Supports all HuggingFace-hosted SentenceTransformer-compatible models.

Thread-safe singleton model loading using threading.Lock ensures the model
is loaded exactly once even under concurrent FastAPI startup conditions.

Automatic device detection priority:
  CUDA (NVIDIA GPU) -> MPS (Apple Silicon) -> CPU
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any

import numpy as np

from app.core.logging import get_logger
from app.embeddings.exceptions import (
    EmbeddingInferenceException,
    EmbeddingModelLoadException,
)
from app.embeddings.models import EmbeddingModelInfo
from app.embeddings.provider import EmbeddingProvider

logger = get_logger(__name__)


def _detect_device() -> str:
    """Detect the best available compute device.

    Priority: CUDA > MPS > CPU

    Returns:
        str: Device string for PyTorch ('cuda', 'mps', or 'cpu').
    """
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


class SentenceTransformerProvider(EmbeddingProvider):
    """Embedding provider backed by sentence-transformers SentenceTransformer.

    Usage:
        provider = SentenceTransformerProvider(model_name="BAAI/bge-base-en-v1.5")
        provider.load()  # Loads model once; thread-safe
        vectors = provider.encode_batch(["text one", "text two"])
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-base-en-v1.5",
        device: str | None = None,
        normalize_embeddings: bool = True,
        cache_folder: str | None = None,
        trust_remote_code: bool = False,
        model_kwargs: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the provider configuration (does NOT load the model yet).

        Args:
            model_name: HuggingFace model identifier or local model directory.
            device: Compute device override. Auto-detected if None.
            normalize_embeddings: Whether to L2-normalize output embeddings.
            cache_folder: Override HuggingFace Hub cache directory.
            trust_remote_code: Pass to transformers for models requiring remote execution.
            model_kwargs: Additional kwargs forwarded to SentenceTransformer constructor.
        """
        self._model_name = model_name
        self._requested_device = device
        self._normalize_embeddings = normalize_embeddings
        self._cache_folder = cache_folder
        self._trust_remote_code = trust_remote_code
        self._model_kwargs = model_kwargs or {}

        self._model: Any = None  # sentence_transformers.SentenceTransformer
        self._model_info: EmbeddingModelInfo | None = None
        self._lock = threading.Lock()
        self._loaded = False

    def load(self) -> None:
        """Load the SentenceTransformer model into memory (thread-safe, idempotent).

        Safe to call multiple times — model is loaded only once. Subsequent calls
        return immediately.

        Raises:
            EmbeddingModelLoadException: If model fails to load.
        """
        if self._loaded:
            return

        with self._lock:
            # Double-checked locking: another thread may have loaded while we waited
            if self._loaded:
                return

            device = self._requested_device or _detect_device()

            logger.info(
                "embedding_model_loading",
                model_name=self._model_name,
                device=device,
            )

            try:
                from sentence_transformers import SentenceTransformer

                kwargs: dict[str, Any] = {
                    "model_name_or_path": self._model_name,
                    "device": device,
                    "trust_remote_code": self._trust_remote_code,
                }
                if self._cache_folder:
                    kwargs["cache_folder"] = self._cache_folder
                if self._model_kwargs:
                    kwargs.update(self._model_kwargs)

                self._model = SentenceTransformer(**kwargs)

            except Exception as exc:
                raise EmbeddingModelLoadException(
                    model_name=self._model_name,
                    reason=str(exc),
                ) from exc

            # Resolve actual dimension and max sequence length
            try:
                dimension: int = self._model.get_sentence_embedding_dimension() or 768
                max_seq_length: int = getattr(self._model, "max_seq_length", 512)
            except Exception:
                dimension = 768
                max_seq_length = 512

            resolved_device = device
            try:
                resolved_device = str(next(self._model.parameters()).device)
            except Exception:
                pass

            self._model_info = EmbeddingModelInfo(
                model_name=self._model_name,
                provider="SentenceTransformerProvider",
                dimension=dimension,
                max_seq_length=max_seq_length,
                device=resolved_device,
                normalize_embeddings=self._normalize_embeddings,
                loaded_at=datetime.now(UTC),
            )

            self._loaded = True

            logger.info(
                "embedding_model_loaded",
                model_name=self._model_name,
                dimension=dimension,
                device=resolved_device,
                max_seq_length=max_seq_length,
            )

    def _ensure_loaded(self) -> None:
        """Auto-load model if not yet loaded."""
        if not self._loaded:
            self.load()

    @property
    def model_info(self) -> EmbeddingModelInfo:
        """Return metadata about the loaded model."""
        self._ensure_loaded()
        assert self._model_info is not None
        return self._model_info

    @property
    def is_loaded(self) -> bool:
        """Return whether the model has been loaded."""
        return self._loaded

    def encode_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
        normalize: bool = True,
        show_progress: bool = False,
    ) -> np.ndarray:
        """Encode a list of texts into embedding vectors.

        Args:
            texts: Non-empty list of text strings.
            batch_size: Per-batch inference size for SentenceTransformer.
            normalize: If True, L2-normalize each output vector.
            show_progress: If True, show tqdm progress bars.

        Returns:
            np.ndarray: Shape (len(texts), dimension), dtype float32.

        Raises:
            EmbeddingInferenceException: On model inference failure.
        """
        self._ensure_loaded()

        try:
            result = self._model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=normalize and self._normalize_embeddings,
                show_progress_bar=show_progress,
                convert_to_numpy=True,
            )

            vectors: np.ndarray = np.array(result, dtype=np.float32)

            # Always L2-normalize if requested, even if model doesn't do it natively
            if normalize and not self._normalize_embeddings:
                vectors = self.normalize_vectors(vectors)

            return vectors

        except Exception as exc:
            raise EmbeddingInferenceException(
                reason=str(exc),
                model_name=self._model_name,
            ) from exc

    def encode_single(
        self,
        text: str,
        normalize: bool = True,
    ) -> np.ndarray:
        """Encode a single text string.

        Args:
            text: Input text.
            normalize: If True, L2-normalize output vector.

        Returns:
            np.ndarray: Shape (dimension,), dtype float32.
        """
        result = self.encode_batch([text], batch_size=1, normalize=normalize)
        return result[0]
