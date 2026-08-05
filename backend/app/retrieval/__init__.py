"""Enterprise Hybrid Retrieval Engine.

Combines Dense Vector Similarity Search (Qdrant), Sparse BM25 Keyword Search,
and Reciprocal Rank Fusion (RRF) with metadata filtering, error isolation,
in-memory caching, and observability tracing.
"""

from app.retrieval.bm25 import BM25Index, BM25RetrievalStrategy
from app.retrieval.cache import InMemoryRetrievalCache, RetrievalCache
from app.retrieval.dense import DenseRetrievalStrategy
from app.retrieval.exceptions import (
    DenseRetrievalException,
    FusionException,
    FusionStrategyNotFoundException,
    InvalidQueryException,
    RetrievalCancelledException,
    RetrievalException,
    RetrievalTimeoutException,
    SparseRetrievalException,
    StrategyNotFoundException,
)
from app.retrieval.fusion import (
    CombSUMFusion,
    FusionEngine,
    FusionStrategy,
    ReciprocalRankFusion,
    ScoreNormalizer,
    WeightedLinearFusion,
)
from app.retrieval.models import (
    CandidateChunk,
    RetrievalMetrics,
    RetrievalResult,
    RetrievalTrace,
    RetrievedChunk,
    SearchFilters,
    SearchOptions,
    SearchQuery,
)
from app.retrieval.query_preprocessor import QueryPreprocessor
from app.retrieval.retriever import HybridRetriever
from app.retrieval.service import RetrievalService, create_retrieval_service
from app.retrieval.strategies import RetrievalStrategy, StrategyRegistry

__all__ = [
    "BM25Index",
    "BM25RetrievalStrategy",
    "CandidateChunk",
    "CombSUMFusion",
    "DenseRetrievalException",
    "DenseRetrievalStrategy",
    "FusionEngine",
    "FusionException",
    "FusionStrategy",
    "FusionStrategyNotFoundException",
    "HybridRetriever",
    "InMemoryRetrievalCache",
    "InvalidQueryException",
    "QueryPreprocessor",
    "ReciprocalRankFusion",
    "RetrievalCache",
    "RetrievalCancelledException",
    "RetrievalException",
    "RetrievalMetrics",
    "RetrievalResult",
    "RetrievalService",
    "RetrievalStrategy",
    "RetrievalTimeoutException",
    "RetrievalTrace",
    "RetrievedChunk",
    "ScoreNormalizer",
    "SearchFilters",
    "SearchOptions",
    "SearchQuery",
    "SparseRetrievalException",
    "StrategyNotFoundException",
    "StrategyRegistry",
    "WeightedLinearFusion",
    "create_retrieval_service",
]
