"""Retrieval Application Service Facade.

Provides a unified, dependency-injectable service facade for hybrid, dense-only,
and sparse-only document chunk retrieval.
"""

from __future__ import annotations

from app.core.config import RetrievalSettings, Settings, get_settings
from app.core.logging import get_logger
from app.embeddings.embedding_service import EmbeddingService
from app.retrieval.bm25 import BM25Index, BM25RetrievalStrategy
from app.retrieval.cache import InMemoryRetrievalCache, RetrievalCache
from app.retrieval.dense import DenseRetrievalStrategy
from app.retrieval.fusion import FusionEngine
from app.retrieval.models import (
    RetrievalResult,
    SearchFilters,
    SearchOptions,
    SearchQuery,
)
from app.retrieval.query_preprocessor import QueryPreprocessor
from app.retrieval.retriever import HybridRetriever
from app.retrieval.strategies import StrategyRegistry
from app.vectorstore.vector_repository import VectorRepository

logger = get_logger(__name__)


class RetrievalService:
    """Application service coordinating hybrid document retrieval."""

    def __init__(
        self,
        retriever: HybridRetriever,
        settings: RetrievalSettings | None = None,
    ) -> None:
        """Initialize RetrievalService.

        Args:
            retriever: Configured HybridRetriever instance.
            settings: Retrieval configuration settings.
        """
        self._retriever = retriever
        self._settings = settings or RetrievalSettings()

    @property
    def retriever(self) -> HybridRetriever:
        """Access underlying retriever orchestrator."""
        return self._retriever

    async def search(
        self,
        query: str | SearchQuery,
        options: SearchOptions | None = None,
        filters: SearchFilters | None = None,
    ) -> RetrievalResult:
        """Execute hybrid retrieval across active strategies."""
        return await self._retriever.search(
            query=query, options=options, filters=filters
        )

    async def search_hybrid(
        self,
        query: str,
        top_k: int = 20,
        filters: SearchFilters | None = None,
        dense_weight: float = 0.5,
        sparse_weight: float = 0.5,
    ) -> RetrievalResult:
        """Convenience method for balanced hybrid search."""
        options = SearchOptions(
            top_k=top_k,
            enabled_dense=True,
            enabled_sparse=True,
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
        )
        return await self._retriever.search(
            query=query, options=options, filters=filters
        )

    async def search_dense_only(
        self,
        query: str,
        top_k: int = 20,
        filters: SearchFilters | None = None,
    ) -> RetrievalResult:
        """Execute dense vector similarity retrieval only."""
        options = SearchOptions(
            top_k=top_k,
            enabled_dense=True,
            enabled_sparse=False,
            dense_weight=1.0,
            sparse_weight=0.0,
        )
        return await self._retriever.search(
            query=query, options=options, filters=filters
        )

    async def search_sparse_only(
        self,
        query: str,
        top_k: int = 20,
        filters: SearchFilters | None = None,
    ) -> RetrievalResult:
        """Execute BM25 keyword lexical retrieval only."""
        options = SearchOptions(
            top_k=top_k,
            enabled_dense=False,
            enabled_sparse=True,
            dense_weight=0.0,
            sparse_weight=1.0,
        )
        return await self._retriever.search(
            query=query, options=options, filters=filters
        )


def create_retrieval_service(
    embedding_service: EmbeddingService,
    vector_repository: VectorRepository,
    bm25_index: BM25Index | None = None,
    settings: Settings | None = None,
) -> RetrievalService:
    """Factory helper to construct a production RetrievalService with all dependencies.

    Args:
        embedding_service: EmbeddingService provider instance.
        vector_repository: VectorRepository provider instance.
        bm25_index: Optional pre-populated BM25 inverted index.
        settings: Application root settings.

    Returns:
        RetrievalService: Fully configured service ready for FastAPI DI.
    """
    root_settings = settings or get_settings()
    retrieval_settings = root_settings.retrieval

    # Initialize strategies
    dense_strategy = DenseRetrievalStrategy(
        embedding_service=embedding_service,
        vector_repository=vector_repository,
    )
    bm25_strategy = BM25RetrievalStrategy(
        index=bm25_index,
        k1=retrieval_settings.bm25_k1,
        b=retrieval_settings.bm25_b,
        epsilon=retrieval_settings.bm25_epsilon,
    )

    registry = StrategyRegistry()
    registry.register(dense_strategy)
    registry.register(bm25_strategy)

    fusion_engine = FusionEngine()
    preprocessor = QueryPreprocessor(
        max_query_length=retrieval_settings.max_query_length
    )

    cache: RetrievalCache | None = None
    if retrieval_settings.enable_cache:
        cache = InMemoryRetrievalCache(
            default_ttl_seconds=retrieval_settings.cache_ttl_seconds,
            max_size=retrieval_settings.cache_max_size,
        )

    retriever = HybridRetriever(
        strategy_registry=registry,
        fusion_engine=fusion_engine,
        query_preprocessor=preprocessor,
        cache=cache,
        settings=retrieval_settings,
    )

    return RetrievalService(retriever=retriever, settings=retrieval_settings)
