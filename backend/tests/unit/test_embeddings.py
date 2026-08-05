"""Unit Tests for the Embedding Engine Subsystem.

Covers:
- Models: EmbeddingVector, BatchEmbeddingResult, EmbeddingModelInfo schema validation
- Exceptions: EmbeddingException hierarchy, status codes, details mapping
- Batching: iter_batches, iter_batches_with_indices, compute_adaptive_batch_size, validate_texts
- Provider Abstraction: MockProvider conforming to EmbeddingProvider ABC
- Normalization: L2 normalization correctness and zero-norm protection
- SentenceTransformerProvider: Thread-safe loading, device detection, error handling
- EmbeddingService: Synchronous and asynchronous embedding of single/batch texts
- Adaptive batch size resolution and throughput metrics
- Configuration: EmbeddingSettings, create_embedding_service factory, settings integration
"""

from __future__ import annotations

import threading
import uuid
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.core.config import EmbeddingSettings, get_settings
from app.embeddings import (
    BatchEmbeddingResult,
    EmbeddingDimensionMismatchException,
    EmbeddingException,
    EmbeddingInferenceException,
    EmbeddingModelInfo,
    EmbeddingModelLoadException,
    EmbeddingProvider,
    EmbeddingProviderNotConfiguredException,
    EmbeddingService,
    EmbeddingVector,
    EmptyEmbeddingInputException,
    SentenceTransformerProvider,
    compute_adaptive_batch_size,
    create_embedding_service,
    iter_batches,
    iter_batches_with_indices,
    validate_texts,
)

# ---------------------------------------------------------------------------
# Test Fixtures & Mock Provider
# ---------------------------------------------------------------------------


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic mock provider for unit testing without downloading model weights."""

    def __init__(
        self,
        model_name: str = "mock-embedding-model",
        dimension: int = 384,
        max_seq_length: int = 256,
        device: str = "cpu",
        normalize: bool = True,
        should_fail_encode: bool = False,
    ) -> None:
        self._model_name = model_name
        self._dimension = dimension
        self._max_seq_length = max_seq_length
        self._device = device
        self._normalize = normalize
        self._should_fail_encode = should_fail_encode
        self._load_count = 0

    @property
    def model_info(self) -> EmbeddingModelInfo:
        return EmbeddingModelInfo(
            model_name=self._model_name,
            provider="MockEmbeddingProvider",
            dimension=self._dimension,
            max_seq_length=self._max_seq_length,
            device=self._device,
            normalize_embeddings=self._normalize,
        )

    def encode_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
        normalize: bool = True,
        show_progress: bool = False,
    ) -> np.ndarray:
        if self._should_fail_encode:
            raise EmbeddingInferenceException(
                reason="Simulated hardware inference fault",
                model_name=self._model_name,
            )

        num_texts = len(texts)
        # Generate reproducible pseudo-embeddings based on text length and char codes
        vectors = np.zeros((num_texts, self._dimension), dtype=np.float32)
        for i, text in enumerate(texts):
            seed = sum(ord(c) for c in text)
            np.random.seed(seed % (2**31 - 1))
            vectors[i] = np.random.randn(self._dimension).astype(np.float32)

        if normalize:
            vectors = self.normalize_vectors(vectors)

        return vectors


@pytest.fixture
def mock_provider() -> MockEmbeddingProvider:
    return MockEmbeddingProvider()


@pytest.fixture
def embedding_service(mock_provider: MockEmbeddingProvider) -> EmbeddingService:
    return EmbeddingService(
        provider=mock_provider,
        default_batch_size=16,
        adaptive_batching=True,
        normalize=True,
    )


@pytest.fixture
def sample_texts() -> list[str]:
    return [
        "Investiga is an enterprise AI incident response platform.",
        "Security analysts review forensic logs and triage anomalous alerts.",
        "Role-based access control enforces least privilege policies.",
        "Knowledge retrieval engines index internal investigation playbooks.",
    ]


# ---------------------------------------------------------------------------
# 1. Models & Schemas Tests
# ---------------------------------------------------------------------------


def test_embedding_vector_model() -> None:
    """Verify EmbeddingVector instantiation and field types."""
    vec = EmbeddingVector(
        text_id="test-id-1",
        text="Sample text",
        vector=[0.1, 0.2, 0.3],
        dimension=3,
        model_name="test-model",
        is_normalized=True,
    )
    assert vec.text_id == "test-id-1"
    assert vec.text == "Sample text"
    assert len(vec.vector) == 3
    assert vec.dimension == 3
    assert vec.model_name == "test-model"
    assert vec.is_normalized is True
    assert vec.created_at is not None


def test_batch_embedding_result_model() -> None:
    """Verify BatchEmbeddingResult computes summary statistics properly."""
    result = BatchEmbeddingResult(
        batch_id=uuid.uuid4(),
        embeddings=[],
        total_texts=5,
        successful_embeddings=5,
        model_name="test-model",
        dimension=768,
        latency_ms=45.2,
        throughput_texts_per_sec=110.6,
        metadata={"batch_size": 32},
    )
    assert result.total_texts == 5
    assert result.successful_embeddings == 5
    assert result.dimension == 768
    assert result.latency_ms == 45.2
    assert result.throughput_texts_per_sec == 110.6


def test_embedding_model_info() -> None:
    """Verify EmbeddingModelInfo structure."""
    info = EmbeddingModelInfo(
        model_name="BAAI/bge-base-en-v1.5",
        provider="SentenceTransformerProvider",
        dimension=768,
        max_seq_length=512,
        device="cpu",
        normalize_embeddings=True,
    )
    assert info.dimension == 768
    assert info.device == "cpu"
    assert info.normalize_embeddings is True


# ---------------------------------------------------------------------------
# 2. Exceptions Hierarchy Tests
# ---------------------------------------------------------------------------


def test_exception_hierarchy() -> None:
    """Verify all custom exceptions inherit from EmbeddingException."""
    exc1 = EmbeddingModelLoadException("bge-base", "File not found")
    exc2 = EmbeddingInferenceException("CUDA OOM", "bge-base")
    exc3 = EmptyEmbeddingInputException()
    exc4 = EmbeddingDimensionMismatchException(expected=768, actual=384)
    exc5 = EmbeddingProviderNotConfiguredException("DummyProvider")

    assert isinstance(exc1, EmbeddingException)
    assert isinstance(exc2, EmbeddingException)
    assert isinstance(exc3, EmbeddingException)
    assert isinstance(exc4, EmbeddingException)
    assert isinstance(exc5, EmbeddingException)

    assert exc3.status_code == 422
    assert exc1.error_code == "EMBEDDING_MODEL_LOAD_FAILED"
    assert exc2.error_code == "EMBEDDING_INFERENCE_FAILED"
    assert exc4.error_code == "EMBEDDING_DIMENSION_MISMATCH"


# ---------------------------------------------------------------------------
# 3. Batching Utilities Tests
# ---------------------------------------------------------------------------


def test_iter_batches() -> None:
    """Verify iter_batches splits list into expected sublists."""
    items = ["a", "b", "c", "d", "e"]
    batches = list(iter_batches(items, batch_size=2))
    assert len(batches) == 3
    assert batches[0] == ["a", "b"]
    assert batches[1] == ["c", "d"]
    assert batches[2] == ["e"]


def test_iter_batches_invalid_size() -> None:
    """Verify ValueError on batch_size <= 0."""
    with pytest.raises(ValueError, match="batch_size must be > 0"):
        list(iter_batches(["a"], batch_size=0))


def test_iter_batches_with_indices() -> None:
    """Verify (offset, batch) pairs produced by iter_batches_with_indices."""
    items = ["x", "y", "z"]
    indexed = list(iter_batches_with_indices(items, batch_size=2))
    assert indexed[0] == (0, ["x", "y"])
    assert indexed[1] == (2, ["z"])


def test_compute_adaptive_batch_size() -> None:
    """Verify adaptive batch size scaling based on text lengths."""
    # Very short texts -> higher batch size
    short_lengths = [20] * 100
    b_short = compute_adaptive_batch_size(
        short_lengths, target_batch_tokens=1000, max_batch_size=64
    )
    assert b_short > 10

    # Very long texts -> lower batch size
    long_lengths = [4000] * 10
    b_long = compute_adaptive_batch_size(
        long_lengths, target_batch_tokens=1000, min_batch_size=1, max_batch_size=64
    )
    assert b_long <= 2


def test_validate_texts_valid(sample_texts: list[str]) -> None:
    """Valid texts pass through stripped."""
    validated = validate_texts(sample_texts)
    assert len(validated) == len(sample_texts)
    assert all(isinstance(t, str) and len(t) > 0 for t in validated)


def test_validate_texts_empty_list() -> None:
    """Empty list raises EmptyEmbeddingInputException."""
    with pytest.raises(EmptyEmbeddingInputException):
        validate_texts([])


def test_validate_texts_whitespace_only() -> None:
    """List containing only whitespace strings raises EmptyEmbeddingInputException."""
    with pytest.raises(EmptyEmbeddingInputException):
        validate_texts(["   ", "\n\t", " "])


# ---------------------------------------------------------------------------
# 4. Normalization Tests
# ---------------------------------------------------------------------------


def test_normalize_vectors_unit_length() -> None:
    """Verify L2 normalization produces vectors with norm == 1.0."""
    raw = np.array([[3.0, 4.0, 0.0], [1.0, 1.0, 1.0]], dtype=np.float32)
    normalized = EmbeddingProvider.normalize_vectors(raw)

    norms = np.linalg.norm(normalized, axis=1)
    np.testing.assert_allclose(norms, np.ones(2, dtype=np.float32), atol=1e-5)


def test_normalize_vectors_zero_norm_protection() -> None:
    """Verify all-zero vector does not raise ZeroDivisionError and remains zeros."""
    zero_vec = np.zeros((1, 4), dtype=np.float32)
    normalized = EmbeddingProvider.normalize_vectors(zero_vec)
    assert np.all(normalized == 0.0)


# ---------------------------------------------------------------------------
# 5. EmbeddingProvider & Mock Tests
# ---------------------------------------------------------------------------


def test_mock_provider_encode_batch(
    mock_provider: MockEmbeddingProvider, sample_texts: list[str]
) -> None:
    """Verify encode_batch produces correct matrix shape and normalized vectors."""
    vectors = mock_provider.encode_batch(sample_texts, batch_size=2, normalize=True)
    assert vectors.shape == (len(sample_texts), mock_provider.dimension)
    assert vectors.dtype == np.float32

    norms = np.linalg.norm(vectors, axis=1)
    np.testing.assert_allclose(norms, np.ones(len(sample_texts)), atol=1e-5)


def test_mock_provider_encode_single(mock_provider: MockEmbeddingProvider) -> None:
    """Verify encode_single produces 1D vector."""
    vec = mock_provider.encode_single("Single text snippet", normalize=True)
    assert vec.shape == (mock_provider.dimension,)
    assert abs(np.linalg.norm(vec) - 1.0) < 1e-5


@pytest.mark.asyncio
async def test_mock_provider_async_methods(
    mock_provider: MockEmbeddingProvider, sample_texts: list[str]
) -> None:
    """Verify encode_batch_async and encode_single_async execute offloaded."""
    batch_res = await mock_provider.encode_batch_async(sample_texts, batch_size=2)
    assert batch_res.shape == (len(sample_texts), mock_provider.dimension)

    single_res = await mock_provider.encode_single_async(sample_texts[0])
    assert single_res.shape == (mock_provider.dimension,)


# ---------------------------------------------------------------------------
# 6. SentenceTransformerProvider Unit Tests (with Mocks)
# ---------------------------------------------------------------------------


def test_sentence_transformer_provider_init() -> None:
    """Provider initializes without loading model immediately."""
    provider = SentenceTransformerProvider(
        model_name="BAAI/bge-base-en-v1.5",
        device="cpu",
        normalize_embeddings=True,
    )
    assert provider.is_loaded is False
    assert provider._model_name == "BAAI/bge-base-en-v1.5"


def test_sentence_transformer_provider_thread_safe_load() -> None:
    """Verify concurrent threads only load the model once."""
    provider = SentenceTransformerProvider(
        model_name="BAAI/bge-small-en-v1.5", device="cpu"
    )

    mock_st_instance = MagicMock()
    mock_st_instance.get_sentence_embedding_dimension.return_value = 384
    mock_st_instance.max_seq_length = 512
    param_mock = MagicMock()
    param_mock.device = "cpu"
    mock_st_instance.parameters.return_value = iter([param_mock])

    with patch(
        "sentence_transformers.SentenceTransformer", return_value=mock_st_instance
    ) as mock_st_cls:
        threads: list[threading.Thread] = []
        for _ in range(10):
            t = threading.Thread(target=provider.load)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert provider.is_loaded is True
        # Constructor should be called exactly once despite 10 threads
        assert mock_st_cls.call_count == 1
        assert provider.dimension == 384
        assert provider.model_info.dimension == 384


def test_sentence_transformer_provider_load_failure() -> None:
    """Verify EmbeddingModelLoadException is raised when sentence_transformers fails."""
    provider = SentenceTransformerProvider(model_name="invalid/non-existent-model")

    with patch(
        "sentence_transformers.SentenceTransformer",
        side_effect=RuntimeError("Model not found"),
    ):
        with pytest.raises(EmbeddingModelLoadException) as exc_info:
            provider.load()

        assert "invalid/non-existent-model" in exc_info.value.message
        assert exc_info.value.error_code == "EMBEDDING_MODEL_LOAD_FAILED"


def test_sentence_transformer_provider_inference_failure() -> None:
    """Verify EmbeddingInferenceException when encode fails."""
    provider = SentenceTransformerProvider(
        model_name="BAAI/bge-base-en-v1.5", device="cpu"
    )

    mock_model = MagicMock()
    mock_model.get_sentence_embedding_dimension.return_value = 768
    mock_model.max_seq_length = 512
    mock_model.encode.side_effect = RuntimeError("CUDA Out of Memory")
    mock_model.parameters.return_value = iter([MagicMock(device="cpu")])

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
        with pytest.raises(EmbeddingInferenceException) as exc_info:
            provider.encode_batch(["some text"])

        assert "CUDA Out of Memory" in exc_info.value.message


# ---------------------------------------------------------------------------
# 7. EmbeddingService Tests (Sync & Async)
# ---------------------------------------------------------------------------


def test_embedding_service_embed_text_single(
    embedding_service: EmbeddingService,
) -> None:
    """Verify embed_text single string execution."""
    res = embedding_service.embed_text(
        "Incident response automation", text_id="doc-123"
    )
    assert isinstance(res, EmbeddingVector)
    assert res.text_id == "doc-123"
    assert res.text == "Incident response automation"
    assert len(res.vector) == embedding_service.dimension
    assert res.is_normalized is True


def test_embedding_service_embed_text_empty_input(
    embedding_service: EmbeddingService,
) -> None:
    """Verify empty/blank string raises EmptyEmbeddingInputException."""
    with pytest.raises(EmptyEmbeddingInputException):
        embedding_service.embed_text("   ")


def test_embedding_service_embed_texts_batch(
    embedding_service: EmbeddingService,
    sample_texts: list[str],
) -> None:
    """Verify batch embedding produces full BatchEmbeddingResult with metrics."""
    custom_ids = [f"id-{i}" for i in range(len(sample_texts))]
    res = embedding_service.embed_texts(sample_texts, text_ids=custom_ids, batch_size=2)

    assert isinstance(res, BatchEmbeddingResult)
    assert res.total_texts == len(sample_texts)
    assert res.successful_embeddings == len(sample_texts)
    assert len(res.embeddings) == len(sample_texts)
    assert res.dimension == embedding_service.dimension
    assert res.latency_ms >= 0.0
    assert res.throughput_texts_per_sec >= 0.0

    for i, emb in enumerate(res.embeddings):
        assert emb.text_id == f"id-{i}"
        assert emb.text == sample_texts[i]
        assert len(emb.vector) == embedding_service.dimension


@pytest.mark.asyncio
async def test_embedding_service_async_methods(
    embedding_service: EmbeddingService,
    sample_texts: list[str],
) -> None:
    """Verify async single and batch embedding execution."""
    single_res = await embedding_service.embed_text_async(
        sample_texts[0], text_id="async-1"
    )
    assert isinstance(single_res, EmbeddingVector)
    assert single_res.text_id == "async-1"

    batch_res = await embedding_service.embed_texts_async(sample_texts)
    assert isinstance(batch_res, BatchEmbeddingResult)
    assert batch_res.total_texts == len(sample_texts)


def test_embedding_service_properties(embedding_service: EmbeddingService) -> None:
    """Verify model_info and dimension property delegation."""
    assert embedding_service.dimension == 384
    assert embedding_service.model_info.provider == "MockEmbeddingProvider"


# ---------------------------------------------------------------------------
# 8. Configuration & Factory Tests
# ---------------------------------------------------------------------------


def test_embedding_settings_defaults() -> None:
    """Verify EmbeddingSettings defaults align with architectural requirements."""
    cfg = EmbeddingSettings()
    assert cfg.model_name == "BAAI/bge-base-en-v1.5"
    assert cfg.dimension == 768
    assert cfg.batch_size == 32
    assert cfg.max_seq_length == 512
    assert cfg.normalize_embeddings is True
    assert cfg.adaptive_batching is True


def test_root_settings_contains_embeddings() -> None:
    """Verify Settings contains the embeddings domain configuration."""
    settings = get_settings()
    assert hasattr(settings, "embeddings")
    assert isinstance(settings.embeddings, EmbeddingSettings)
    assert settings.embeddings.model_name == "BAAI/bge-base-en-v1.5"


def test_create_embedding_service_factory() -> None:
    """Verify create_embedding_service builds a functioning service from settings."""
    mock_st_instance = MagicMock()
    mock_st_instance.get_sentence_embedding_dimension.return_value = 768
    mock_st_instance.max_seq_length = 512
    mock_st_instance.parameters.return_value = iter([MagicMock(device="cpu")])

    with patch(
        "sentence_transformers.SentenceTransformer", return_value=mock_st_instance
    ):
        service = create_embedding_service(
            model_name="BAAI/bge-base-en-v1.5",
            auto_load=True,
        )
        assert isinstance(service, EmbeddingService)
        assert isinstance(service._provider, SentenceTransformerProvider)
        assert service.dimension == 768
