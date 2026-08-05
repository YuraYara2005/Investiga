"""Vector Database Infrastructure Subsystem for Investiga.

Provides pluggable vector store provider abstractions, Qdrant implementation,
VectorRepository, VectorIndexManager, MetadataFilterBuilder, and rich multi-tenant models.
"""

from __future__ import annotations

from app.vectorstore.exceptions import (
    CollectionAlreadyExistsException,
    CollectionNotFoundException,
    InvalidFilterException,
    VectorDeleteException,
    VectorDimensionMismatchException,
    VectorQueryException,
    VectorStoreConnectionException,
    VectorStoreException,
    VectorUpsertException,
)
from app.vectorstore.filters import FilterCondition, MetadataFilterBuilder
from app.vectorstore.models import (
    CollectionStats,
    DistanceMetric,
    ScoredVectorRecord,
    VectorPayload,
    VectorRecord,
    VectorSearchResult,
)
from app.vectorstore.provider import VectorStoreProvider
from app.vectorstore.qdrant_provider import QdrantProvider
from app.vectorstore.vector_index_manager import VectorIndexManager
from app.vectorstore.vector_repository import VectorRepository

__all__ = [
    "CollectionAlreadyExistsException",
    "CollectionNotFoundException",
    "CollectionStats",
    "DistanceMetric",
    "FilterCondition",
    "InvalidFilterException",
    "MetadataFilterBuilder",
    "QdrantProvider",
    "ScoredVectorRecord",
    "VectorDeleteException",
    "VectorDimensionMismatchException",
    "VectorIndexManager",
    "VectorPayload",
    "VectorQueryException",
    "VectorRecord",
    "VectorRepository",
    "VectorSearchResult",
    "VectorStoreConnectionException",
    "VectorStoreException",
    "VectorStoreProvider",
    "VectorUpsertException",
]
