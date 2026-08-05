"""Vector Store Provider Abstract Interface.

Defines the contract for pluggable vector store backends (Qdrant, Milvus, Pinecone,
Weaviate, FAISS) ensuring strict domain isolation and clean architecture.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from app.vectorstore.filters import MetadataFilterBuilder
from app.vectorstore.models import (
    CollectionStats,
    DistanceMetric,
    VectorRecord,
    VectorSearchResult,
)


class VectorStoreProvider(ABC):
    """Abstract interface defining operations required of any vector database backend."""

    @abstractmethod
    async def create_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: DistanceMetric = DistanceMetric.COSINE,
        replication_factor: int = 1,
        write_consistency: str = "majority",
    ) -> bool:
        """Create a new vector collection / index with the specified parameters."""

    @abstractmethod
    async def delete_collection(self, collection_name: str) -> bool:
        """Delete an existing vector collection and all its indexed points."""

    @abstractmethod
    async def recreate_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: DistanceMetric = DistanceMetric.COSINE,
        replication_factor: int = 1,
        write_consistency: str = "majority",
    ) -> bool:
        """Delete if exists and create a clean collection with the specified configuration."""

    @abstractmethod
    async def collection_exists(self, collection_name: str) -> bool:
        """Check whether the specified collection exists in the vector database."""

    @abstractmethod
    async def get_collection_stats(self, collection_name: str) -> CollectionStats:
        """Retrieve diagnostic counts and status metrics for a collection."""

    @abstractmethod
    async def upsert(
        self,
        collection_name: str,
        records: list[VectorRecord],
        batch_size: int = 100,
    ) -> int:
        """Insert or update a list of vector records in batches."""

    @abstractmethod
    async def delete(
        self,
        collection_name: str,
        point_ids: Sequence[str | uuid.UUID],
    ) -> int:
        """Delete specific vector points by their unique IDs."""

    @abstractmethod
    async def delete_by_filter(
        self,
        collection_name: str,
        filter_builder: MetadataFilterBuilder,
    ) -> int:
        """Delete vector points matching the provided metadata filter criteria."""

    @abstractmethod
    async def retrieve_by_ids(
        self,
        collection_name: str,
        point_ids: Sequence[str | uuid.UUID],
        with_vectors: bool = False,
    ) -> list[VectorRecord]:
        """Retrieve specific vector records by point IDs."""

    @abstractmethod
    async def retrieve_by_filter(
        self,
        collection_name: str,
        filter_builder: MetadataFilterBuilder,
        limit: int = 100,
        offset: int = 0,
        with_vectors: bool = False,
    ) -> list[VectorRecord]:
        """Retrieve vector records matching metadata filter criteria."""

    @abstractmethod
    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: float | None = None,
        filter_builder: MetadataFilterBuilder | None = None,
        with_vectors: bool = False,
    ) -> VectorSearchResult:
        """Perform nearest-neighbor vector similarity search with optional metadata filtering."""

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Perform backend connectivity and health diagnostics."""

    @abstractmethod
    async def close(self) -> None:
        """Gracefully release network connections and client session resources."""
