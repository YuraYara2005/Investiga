"""Comprehensive Unit Tests for Enterprise Hybrid Retrieval Engine.

Tests query preprocessing, BM25 indexing & scoring, dense vector retrieval,
pluggable rank fusion (RRF, Weighted Linear, CombSUM), metadata filtering,
retrieval caching, partial failure resilience, telemetry tracing, and service facades.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import RetrievalSettings
from app.embeddings.embedding_service import EmbeddingService
from app.embeddings.models import EmbeddingModelInfo, EmbeddingVector
from app.retrieval.bm25 import BM25Index, BM25RetrievalStrategy
from app.retrieval.cache import InMemoryRetrievalCache, RetrievalCache
from app.retrieval.dense import DenseRetrievalStrategy
from app.retrieval.exceptions import (
    DenseRetrievalException,
    FusionStrategyNotFoundException,
    InvalidQueryException,
    RetrievalException,
    RetrievalTimeoutException,
)
from app.retrieval.fusion import (
    FusionEngine,
    ReciprocalRankFusion,
    ScoreNormalizer,
    WeightedLinearFusion,
)
from app.retrieval.models import (
    CandidateChunk,
    SearchFilters,
    SearchOptions,
)
from app.retrieval.query_preprocessor import QueryPreprocessor
from app.retrieval.retriever import HybridRetriever
from app.retrieval.service import RetrievalService, create_retrieval_service
from app.retrieval.strategies import RetrievalStrategy, StrategyRegistry
from app.vectorstore.models import ScoredVectorRecord, VectorSearchResult
from app.vectorstore.vector_repository import VectorRepository

# ==============================================================================
# 1. Query Preprocessor Tests
# ==============================================================================


class TestQueryPreprocessor:
    """Test query sanitization, Unicode normalization, and token extraction."""

    def test_normalize_valid_query(self) -> None:
        preprocessor = QueryPreprocessor(max_query_length=100)
        raw = "   Financial \t Report   for  2024 \n  "
        normalized = preprocessor.normalize(raw)
        assert normalized == "Financial Report for 2024"

    def test_normalize_unicode_nfkc(self) -> None:
        preprocessor = QueryPreprocessor()
        # Ligature ﬁ -> fi
        raw = "ﬁnancial résumé"
        normalized = preprocessor.normalize(raw)
        assert "financial" in normalized
        assert "résumé" in normalized or "resume" in normalized

    def test_normalize_strips_control_characters(self) -> None:
        preprocessor = QueryPreprocessor()
        raw = "Hello\x00World\x1fTest"
        normalized = preprocessor.normalize(raw)
        assert normalized == "Hello World Test"

    def test_normalize_empty_or_whitespace_raises(self) -> None:
        preprocessor = QueryPreprocessor()
        with pytest.raises(InvalidQueryException) as exc_info:
            preprocessor.normalize("   \t \n ")
        assert "empty or solely whitespace" in str(exc_info.value.message)

    def test_normalize_none_raises(self) -> None:
        preprocessor = QueryPreprocessor()
        with pytest.raises(InvalidQueryException):
            preprocessor.normalize(None)  # type: ignore[arg-type]

    def test_normalize_exceeds_max_length_raises(self) -> None:
        preprocessor = QueryPreprocessor(max_query_length=20)
        with pytest.raises(InvalidQueryException) as exc_info:
            preprocessor.normalize(
                "This is a query that is definitely longer than 20 characters"
            )
        assert "exceeds limit" in str(exc_info.value.message)

    def test_tokenize_for_sparse_stopwords(self) -> None:
        preprocessor = QueryPreprocessor(remove_stopwords=True)
        tokens = preprocessor.tokenize_for_sparse(
            "What is the quarterly revenue growth?"
        )
        assert "quarterly" in tokens
        assert "revenue" in tokens
        assert "growth" in tokens
        assert "what" not in tokens
        assert "is" not in tokens
        assert "the" not in tokens

    def test_tokenize_all_stopwords_fallback(self) -> None:
        preprocessor = QueryPreprocessor(remove_stopwords=True)
        tokens = preprocessor.tokenize_for_sparse("what is that")
        assert len(tokens) > 0  # Falls back to raw tokens to avoid empty token list

    def test_preprocess_returns_tuple(self) -> None:
        preprocessor = QueryPreprocessor()
        norm, tokens = preprocessor.preprocess("  Enterprise Search System ")
        assert norm == "Enterprise Search System"
        assert "enterprise" in tokens
        assert "search" in tokens
        assert "system" in tokens


# ==============================================================================
# 2. SearchFilters & Metadata Filtering Tests
# ==============================================================================


class TestSearchFilters:
    """Test filter construction, evaluation, and vector filter builder conversion."""

    def test_filters_is_empty(self) -> None:
        filters = SearchFilters()
        assert filters.is_empty() is True

        filters_with_cat = SearchFilters(category="finance")
        assert filters_with_cat.is_empty() is False

    def test_to_filter_builder(self) -> None:
        doc_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        filters = SearchFilters(
            tenant_id=tenant_id,
            document_ids=[doc_id],
            category="finance",
            tags=["annual", "audit"],
            custom_metadata={"status": "approved"},
        )
        builder = filters.to_filter_builder()
        assert builder.is_empty() is False
        filter_dict = builder.to_dict()
        assert len(filter_dict["must"]) >= 4

    def test_matches_dict(self) -> None:
        doc_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        filters = SearchFilters(
            tenant_id=tenant_id,
            document_ids=[doc_id],
            category="finance",
            tags=["audit"],
        )

        matching_payload = {
            "tenant_id": str(tenant_id),
            "document_id": str(doc_id),
            "category": "finance",
            "tags": ["audit", "2024"],
        }
        assert filters.matches_dict(matching_payload) is True

        wrong_cat_payload = dict(matching_payload)
        wrong_cat_payload["category"] = "legal"
        assert filters.matches_dict(wrong_cat_payload) is False

        missing_tag_payload = dict(matching_payload)
        missing_tag_payload["tags"] = ["other"]
        assert filters.matches_dict(missing_tag_payload) is False


# ==============================================================================
# 3. BM25 Sparse Indexing & Search Tests
# ==============================================================================


class TestBM25IndexAndStrategy:
    """Test in-memory BM25 index creation, Robertson-Spärck Jones IDF, and lexical search."""

    @pytest.fixture
    def sample_index(self) -> BM25Index:
        index = BM25Index(k1=1.5, b=0.75, epsilon=0.25)
        index.add_document(
            chunk_id="chunk-1",
            document_id="doc-1",
            text="Financial report showing quarterly revenue growth and balance sheet assets.",
            chunk_index=0,
            category="finance",
            tags=["quarterly", "revenue"],
        )
        index.add_document(
            chunk_id="chunk-2",
            document_id="doc-2",
            text="Legal contract terms and non-disclosure obligations for enterprise vendors.",
            chunk_index=0,
            category="legal",
            tags=["contract"],
        )
        index.add_document(
            chunk_id="chunk-3",
            document_id="doc-1",
            text="Quarterly revenue breakdown by geographic region and enterprise customer segments.",
            chunk_index=1,
            category="finance",
            tags=["quarterly", "geographic"],
        )
        return index

    def test_bm25_index_counts(self, sample_index: BM25Index) -> None:
        assert sample_index.total_documents == 3

    def test_bm25_search_scoring(self, sample_index: BM25Index) -> None:
        results = sample_index.search(tokens=["revenue", "quarterly"], limit=10)
        assert len(results) >= 2
        # chunk-3 and chunk-1 contain both terms, chunk-2 does not
        matched_chunk_ids = [doc.chunk_id for doc, score in results]
        assert "chunk-1" in matched_chunk_ids
        assert "chunk-3" in matched_chunk_ids
        assert "chunk-2" not in matched_chunk_ids
        assert results[0][1] > 0.0

    def test_bm25_search_with_metadata_filter(self, sample_index: BM25Index) -> None:
        # Search for revenue with legal filter -> should match nothing
        filters = SearchFilters(category="legal")
        results = sample_index.search(tokens=["revenue"], limit=10, filters=filters)
        assert len(results) == 0

        # Search for revenue with finance filter -> should match chunks 1 & 3
        filters_finance = SearchFilters(category="finance")
        results_fin = sample_index.search(
            tokens=["revenue"], limit=10, filters=filters_finance
        )
        assert len(results_fin) == 2

    def test_bm25_search_empty_or_oov(self, sample_index: BM25Index) -> None:
        assert sample_index.search(tokens=[], limit=10) == []
        assert (
            sample_index.search(tokens=["xenomorph", "cryptocurrency"], limit=10) == []
        )

    @pytest.mark.asyncio
    async def test_bm25_retrieval_strategy(self, sample_index: BM25Index) -> None:
        strategy = BM25RetrievalStrategy(index=sample_index)
        assert strategy.name == "bm25"

        options = SearchOptions(sparse_candidate_limit=5)
        candidates = await strategy.retrieve(
            query="quarterly revenue",
            normalized_query="quarterly revenue",
            tokens=["quarterly", "revenue"],
            options=options,
        )
        assert len(candidates) >= 2
        assert candidates[0].strategy_name == "bm25"
        assert candidates[0].rank == 1
        assert candidates[0].score >= candidates[1].score


# ==============================================================================
# 4. Pluggable Fusion & Score Normalizer Tests
# ==============================================================================


class TestScoreNormalizerAndFusion:
    """Test score normalization and rank fusion strategies."""

    def test_min_max_normalize(self) -> None:
        scores = [10.0, 20.0, 30.0]
        norm = ScoreNormalizer.min_max_normalize(scores)
        assert norm == [0.0, 0.5, 1.0]

        # Single score or identical scores
        assert ScoreNormalizer.min_max_normalize([5.0, 5.0]) == [1.0, 1.0]
        assert ScoreNormalizer.min_max_normalize([]) == []

    def test_z_score_normalize(self) -> None:
        scores = [10.0, 20.0, 30.0]
        norm = ScoreNormalizer.z_score_normalize(scores)
        assert len(norm) == 3
        assert all(0.0 < s < 1.0 for s in norm)
        assert norm[0] < norm[1] < norm[2]

    def test_reciprocal_rank_fusion(self) -> None:
        rrf = ReciprocalRankFusion()
        assert rrf.name == "rrf"

        cand_dense_1 = CandidateChunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            text="Dense text 1",
            score=0.95,
            rank=1,
            strategy_name="dense",
            heading="Intro",
        )
        cand_dense_2 = CandidateChunk(
            chunk_id="chunk-2",
            document_id="doc-2",
            text="Dense text 2",
            score=0.85,
            rank=2,
            strategy_name="dense",
        )
        cand_sparse_1 = CandidateChunk(
            chunk_id="chunk-2",
            document_id="doc-2",
            text="Dense text 2",
            score=12.5,
            rank=1,
            strategy_name="bm25",
        )
        cand_sparse_3 = CandidateChunk(
            chunk_id="chunk-3",
            document_id="doc-3",
            text="Sparse text 3",
            score=8.0,
            rank=2,
            strategy_name="bm25",
        )

        candidates = {
            "dense": [cand_dense_1, cand_dense_2],
            "bm25": [cand_sparse_1, cand_sparse_3],
        }

        options = SearchOptions(
            top_k=10,
            dense_weight=0.5,
            sparse_weight=0.5,
            rrf_k=60,
        )

        fused = rrf.fuse(candidates, options)
        assert len(fused) == 3

        # chunk-2 appeared in both dense (rank 2) and sparse (rank 1):
        # rrf score for chunk-2 = 0.5 * (1/62) + 0.5 * (1/61)
        # rrf score for chunk-1 = 0.5 * (1/61)
        # chunk-2 must rank #1
        assert fused[0].chunk_id == "chunk-2"
        assert sorted(fused[0].retrieval_sources) == ["bm25", "dense"]
        assert fused[0].dense_rank == 2
        assert fused[0].sparse_rank == 1
        assert fused[0].dense_score == 0.85
        assert fused[0].sparse_score == 12.5

    def test_weighted_linear_fusion(self) -> None:
        linear = WeightedLinearFusion()
        assert linear.name == "weighted_linear"

        cand_dense = CandidateChunk(
            chunk_id="c1",
            document_id="d1",
            text="T1",
            score=0.9,
            rank=1,
            strategy_name="dense",
        )
        cand_sparse = CandidateChunk(
            chunk_id="c1",
            document_id="d1",
            text="T1",
            score=10.0,
            rank=1,
            strategy_name="bm25",
        )

        candidates = {"dense": [cand_dense], "bm25": [cand_sparse]}
        options = SearchOptions(dense_weight=0.5, sparse_weight=0.5)
        fused = linear.fuse(candidates, options)
        assert len(fused) == 1
        assert fused[0].chunk_id == "c1"

    def test_fusion_engine_registry(self) -> None:
        engine = FusionEngine()
        assert engine.get("rrf").name == "rrf"
        assert engine.get("weighted_linear").name == "weighted_linear"
        assert engine.get("combsum").name == "combsum"

        with pytest.raises(FusionStrategyNotFoundException):
            engine.get("unknown_fusion_algorithm")


# ==============================================================================
# 5. Lightweight Cache Tests
# ==============================================================================


class TestRetrievalCache:
    """Test in-memory cache operations, TTL expiration, and LRU eviction."""

    @pytest.mark.asyncio
    async def test_cache_set_get_delete_clear(self) -> None:
        cache = InMemoryRetrievalCache(default_ttl_seconds=60, max_size=10)
        await cache.set("k1", {"data": "v1"})
        val = await cache.get("k1")
        assert val == {"data": "v1"}

        deleted = await cache.delete("k1")
        assert deleted is True
        assert await cache.get("k1") is None

        await cache.set("k2", "v2")
        await cache.clear()
        assert await cache.get("k2") is None

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self) -> None:
        # TTL of 0.05 seconds
        cache = InMemoryRetrievalCache(default_ttl_seconds=1, max_size=10)
        await cache.set("k_expire", "val", ttl_seconds=0)  # expires immediately
        val = await cache.get("k_expire")
        assert val is None

    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self) -> None:
        cache = InMemoryRetrievalCache(default_ttl_seconds=300, max_size=2)
        await cache.set("k1", "v1")
        await cache.set("k2", "v2")
        # Access k1 to make k2 older
        await cache.get("k1")
        # Insert k3 -> should evict k2
        await cache.set("k3", "v3")

        assert await cache.get("k1") == "v1"
        assert await cache.get("k3") == "v3"
        assert await cache.get("k2") is None

    def test_build_cache_key_deterministic(self) -> None:
        filters = SearchFilters(category="finance")
        options = SearchOptions(top_k=10)
        key1 = RetrievalCache.build_cache_key("revenue growth", filters, options)
        key2 = RetrievalCache.build_cache_key("revenue growth", filters, options)
        assert key1 == key2
        assert key1.startswith("retrieval:")


# ==============================================================================
# 6. Dense Retrieval Strategy Tests
# ==============================================================================


class TestDenseRetrievalStrategy:
    """Test dense vector similarity retrieval with mock dependencies."""

    @pytest.mark.asyncio
    async def test_dense_retrieval_success(self) -> None:
        mock_embedding_service = MagicMock(spec=EmbeddingService)
        mock_embedding_service.model_info = EmbeddingModelInfo(
            model_name="BAAI/bge-base-en-v1.5",
            provider="SentenceTransformerProvider",
            dimension=768,
            max_seq_length=512,
            normalize_embeddings=True,
            device="cpu",
        )
        mock_embedding_service.embed_text_async = AsyncMock(
            return_value=EmbeddingVector(
                text_id="query-1",
                text="financial results",
                vector=[0.1] * 768,
                dimension=768,
                model_name="BAAI/bge-base-en-v1.5",
            )
        )

        mock_vector_repo = MagicMock(spec=VectorRepository)
        mock_vector_repo.default_collection_name = "investiga_knowledge"
        mock_vector_repo.search = AsyncMock(
            return_value=VectorSearchResult(
                collection_name="investiga_knowledge",
                query_vector_dim=768,
                results=[
                    ScoredVectorRecord(
                        id=str(uuid.uuid4()),
                        score=0.92,
                        payload={
                            "chunk_id": "c100",
                            "document_id": "d100",
                            "raw_text": "Sample financial chunk text",
                            "heading": "Section 1",
                            "category": "finance",
                        },
                    )
                ],
                total_found=1,
                latency_ms=15.0,
            )
        )

        strategy = DenseRetrievalStrategy(
            embedding_service=mock_embedding_service,
            vector_repository=mock_vector_repo,
        )
        assert strategy.name == "dense"
        assert strategy.embedding_model_name == "BAAI/bge-base-en-v1.5"

        options = SearchOptions(dense_candidate_limit=10)
        candidates = await strategy.retrieve(
            query="financial results",
            normalized_query="financial results",
            tokens=["financial", "results"],
            options=options,
        )

        assert len(candidates) == 1
        assert candidates[0].chunk_id == "c100"
        assert candidates[0].score == 0.92
        assert candidates[0].strategy_name == "dense"
        assert candidates[0].heading == "Section 1"

    @pytest.mark.asyncio
    async def test_dense_retrieval_failure_raises_dense_exception(self) -> None:
        mock_embedding_service = MagicMock(spec=EmbeddingService)
        mock_embedding_service.embed_text_async = AsyncMock(
            side_effect=RuntimeError("CUDA out of memory")
        )
        mock_vector_repo = MagicMock(spec=VectorRepository)

        strategy = DenseRetrievalStrategy(
            embedding_service=mock_embedding_service,
            vector_repository=mock_vector_repo,
        )

        with pytest.raises(DenseRetrievalException) as exc_info:
            await strategy.retrieve(
                query="test",
                normalized_query="test",
                tokens=["test"],
                options=SearchOptions(),
            )
        assert "CUDA out of memory" in str(exc_info.value.message)


# ==============================================================================
# 7. Hybrid Retriever & Orchestration Tests
# ==============================================================================


class TestHybridRetriever:
    """Test concurrent execution, partial failure recovery, trace telemetry, and caching."""

    @pytest.fixture
    def mock_dense_strategy(self) -> MagicMock:
        strat = MagicMock(spec=RetrievalStrategy)
        strat.name = "dense"
        strat.embedding_model_name = "mock-model-v1"
        strat.retrieve = AsyncMock(
            return_value=[
                CandidateChunk(
                    chunk_id="chunk-1",
                    document_id="doc-1",
                    text="Dense Text Chunk 1",
                    score=0.95,
                    rank=1,
                    strategy_name="dense",
                    category="finance",
                ),
                CandidateChunk(
                    chunk_id="chunk-2",
                    document_id="doc-2",
                    text="Dense Text Chunk 2",
                    score=0.88,
                    rank=2,
                    strategy_name="dense",
                    category="finance",
                ),
            ]
        )
        return strat

    @pytest.fixture
    def mock_bm25_strategy(self) -> MagicMock:
        strat = MagicMock(spec=RetrievalStrategy)
        strat.name = "bm25"
        strat.retrieve = AsyncMock(
            return_value=[
                CandidateChunk(
                    chunk_id="chunk-2",
                    document_id="doc-2",
                    text="Dense Text Chunk 2",
                    score=15.0,
                    rank=1,
                    strategy_name="bm25",
                    category="finance",
                ),
                CandidateChunk(
                    chunk_id="chunk-3",
                    document_id="doc-3",
                    text="BM25 Text Chunk 3",
                    score=9.5,
                    rank=2,
                    strategy_name="bm25",
                    category="finance",
                ),
            ]
        )
        return strat

    @pytest.mark.asyncio
    async def test_hybrid_search_end_to_end(
        self,
        mock_dense_strategy: MagicMock,
        mock_bm25_strategy: MagicMock,
    ) -> None:
        registry = StrategyRegistry()
        registry.register(mock_dense_strategy)
        registry.register(mock_bm25_strategy)

        retriever = HybridRetriever(
            strategy_registry=registry,
            fusion_engine=FusionEngine(),
            query_preprocessor=QueryPreprocessor(),
            settings=RetrievalSettings(enable_cache=True),
        )

        result = await retriever.search("quarterly revenue report")

        assert result.query == "quarterly revenue report"
        assert result.normalized_query == "quarterly revenue report"
        assert len(result.chunks) == 3
        # Chunk 2 appeared in both, should be ranked 1st
        assert result.chunks[0].chunk_id == "chunk-2"
        assert sorted(result.chunks[0].retrieval_sources) == ["bm25", "dense"]

        # Verify trace
        trace = result.trace
        assert trace is not None
        assert trace.partial_failure is False
        assert trace.cache_hit is False
        assert trace.dense_candidates == 2
        assert trace.sparse_candidates == 2
        assert trace.returned_chunks == 3
        assert "prep" in trace.latencies
        assert "fusion" in trace.latencies

        # Verify metrics
        assert result.metrics.total_duration_ms > 0
        assert result.metrics.returned_chunks_count == 3

    @pytest.mark.asyncio
    async def test_hybrid_search_cache_hit(
        self,
        mock_dense_strategy: MagicMock,
        mock_bm25_strategy: MagicMock,
    ) -> None:
        registry = StrategyRegistry()
        registry.register(mock_dense_strategy)
        registry.register(mock_bm25_strategy)
        cache = InMemoryRetrievalCache()

        retriever = HybridRetriever(
            strategy_registry=registry,
            cache=cache,
            settings=RetrievalSettings(enable_cache=True),
        )

        # 1st search -> cache miss, populates cache
        res1 = await retriever.search("annual compliance audit")
        assert res1.trace is not None and res1.trace.cache_hit is False

        # 2nd search -> cache hit
        res2 = await retriever.search("annual compliance audit")
        assert res2.trace is not None and res2.trace.cache_hit is True
        assert len(res2.chunks) == len(res1.chunks)
        # Verify strategy retrieve was only called once
        assert mock_dense_strategy.retrieve.call_count == 1

    @pytest.mark.asyncio
    async def test_partial_failure_dense_fails_bm25_succeeds(
        self,
        mock_bm25_strategy: MagicMock,
    ) -> None:
        failing_dense = MagicMock(spec=RetrievalStrategy)
        failing_dense.name = "dense"
        failing_dense.retrieve = AsyncMock(
            side_effect=DenseRetrievalException("Qdrant cluster unavailable")
        )

        registry = StrategyRegistry()
        registry.register(failing_dense)
        registry.register(mock_bm25_strategy)

        retriever = HybridRetriever(strategy_registry=registry)
        result = await retriever.search("fallback test query")

        # Must succeed gracefully with BM25 candidates
        assert len(result.chunks) == 2
        assert result.trace is not None
        assert result.trace.partial_failure is True
        assert any("dense" in msg for msg in result.trace.failure_reasons)

    @pytest.mark.asyncio
    async def test_all_strategies_fail_raises_retrieval_exception(self) -> None:
        failing_dense = MagicMock(spec=RetrievalStrategy)
        failing_dense.name = "dense"
        failing_dense.retrieve = AsyncMock(side_effect=RuntimeError("Dense down"))

        failing_bm25 = MagicMock(spec=RetrievalStrategy)
        failing_bm25.name = "bm25"
        failing_bm25.retrieve = AsyncMock(side_effect=RuntimeError("BM25 down"))

        registry = StrategyRegistry()
        registry.register(failing_dense)
        registry.register(failing_bm25)

        retriever = HybridRetriever(strategy_registry=registry)
        with pytest.raises(RetrievalException) as exc_info:
            await retriever.search("doomed query")
        assert "All retrieval strategies failed" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_retrieval_timeout_raises_timeout_exception(self) -> None:
        async def _slow_retrieve(*args: Any, **kwargs: Any) -> list[CandidateChunk]:
            await asyncio.sleep(0.5)
            return []

        slow_strat = MagicMock(spec=RetrievalStrategy)
        slow_strat.name = "dense"
        slow_strat.retrieve = AsyncMock(side_effect=_slow_retrieve)

        registry = StrategyRegistry()
        registry.register(slow_strat)

        retriever = HybridRetriever(strategy_registry=registry)
        options = SearchOptions(timeout_seconds=0.05)

        with pytest.raises(RetrievalTimeoutException):
            await retriever.search("timeout test", options=options)


# ==============================================================================
# 8. Retrieval Service Facade Tests
# ==============================================================================


class TestRetrievalService:
    """Test service facade and factory helpers."""

    @pytest.mark.asyncio
    async def test_service_facade_methods(self) -> None:
        mock_retriever = MagicMock(spec=HybridRetriever)
        mock_result = MagicMock()
        mock_retriever.search = AsyncMock(return_value=mock_result)

        service = RetrievalService(retriever=mock_retriever)

        # search
        res1 = await service.search("query 1")
        assert res1 == mock_result

        # search_hybrid
        res2 = await service.search_hybrid("query 2", top_k=5)
        assert res2 == mock_result

        # search_dense_only
        res3 = await service.search_dense_only("query 3")
        assert res3 == mock_result

        # search_sparse_only
        res4 = await service.search_sparse_only("query 4")
        assert res4 == mock_result

    def test_create_retrieval_service_factory(self) -> None:
        mock_embed = MagicMock(spec=EmbeddingService)
        mock_repo = MagicMock(spec=VectorRepository)
        mock_repo.default_collection_name = "test_col"

        service = create_retrieval_service(
            embedding_service=mock_embed,
            vector_repository=mock_repo,
        )
        assert isinstance(service, RetrievalService)
        assert isinstance(service.retriever, HybridRetriever)
