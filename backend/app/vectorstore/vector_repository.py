"""Generic Vector Repository Layer.

Provides high-level repository operations for vector persistence, similarity search,
and metadata querying isolated from specific vector database backends.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from app.core.config import VectorStoreSettings
from app.core.logging import get_logger
from app.vectorstore.filters import MetadataFilterBuilder
from app.vectorstore.models import (
    VectorRecord,
    VectorSearchResult,
)
from app.vectorstore.provider import VectorStoreProvider

logger = get_logger(__name__)


class VectorRepository:
    """Generic repository providing domain-agnostic vector storage and query abstractions."""

    def __init__(
        self,
        provider: VectorStoreProvider,
        settings: VectorStoreSettings | None = None,
    ) -> None:
        """Initialize VectorRepository.

        Args:
            provider: VectorStoreProvider concrete implementation.
            settings: VectorStoreSettings configuration instance.
        """
        self._provider = provider
        self._settings = settings or VectorStoreSettings()

    @property
    def default_collection_name(self) -> str:
        """Return the default collection name configured in settings."""
        return self._settings.collection_name

    def _resolve_collection(self, collection_name: str | None) -> str:
        """Resolve effective collection name falling back to default."""
        return collection_name or self.default_collection_name

    async def upsert_vectors(
        self,
        records: list[VectorRecord],
        collection_name: str | None = None,
        batch_size: int = 100,
    ) -> int:
        """Persist or update vector records in batches."""
        target_collection = self._resolve_collection(collection_name)
        return await self._provider.upsert(
            collection_name=target_collection,
            records=records,
            batch_size=batch_size,
        )

    async def save_vectors(
        self,
        records: list[VectorRecord],
        collection_name: str | None = None,
    ) -> int:
        """Convenience alias for upserting vector records."""
        return await self.upsert_vectors(
            records=records, collection_name=collection_name
        )

    async def search(
        self,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: float | None = None,
        filter_builder: MetadataFilterBuilder | None = None,
        collection_name: str | None = None,
        with_vectors: bool = False,
    ) -> VectorSearchResult:
        """Perform nearest-neighbor similarity search against indexed vector records."""
        target_collection = self._resolve_collection(collection_name)
        return await self._provider.search(
            collection_name=target_collection,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            filter_builder=filter_builder,
            with_vectors=with_vectors,
        )

    async def retrieve(
        self,
        filter_builder: MetadataFilterBuilder,
        limit: int = 100,
        offset: int = 0,
        collection_name: str | None = None,
        with_vectors: bool = False,
    ) -> list[VectorRecord]:
        """Retrieve vector records matching metadata filter criteria."""
        target_collection = self._resolve_collection(collection_name)
        return await self._provider.retrieve_by_filter(
            collection_name=target_collection,
            filter_builder=filter_builder,
            limit=limit,
            offset=offset,
            with_vectors=with_vectors,
        )

    async def retrieve_by_ids(
        self,
        point_ids: Sequence[str | uuid.UUID],
        collection_name: str | None = None,
        with_vectors: bool = False,
    ) -> list[VectorRecord]:
        """Retrieve specific vector records by point IDs."""
        target_collection = self._resolve_collection(collection_name)
        return await self._provider.retrieve_by_ids(
            collection_name=target_collection,
            point_ids=point_ids,
            with_vectors=with_vectors,
        )

    async def delete(
        self,
        point_ids: Sequence[str | uuid.UUID],
        collection_name: str | None = None,
    ) -> int:
        """Delete specific vector points by ID."""
        target_collection = self._resolve_collection(collection_name)
        return await self._provider.delete(
            collection_name=target_collection,
            point_ids=point_ids,
        )

    async def delete_by_filter(
        self,
        filter_builder: MetadataFilterBuilder,
        collection_name: str | None = None,
    ) -> int:
        """Delete vector points matching the provided metadata filter criteria."""
        target_collection = self._resolve_collection(collection_name)
        return await self._provider.delete_by_filter(
            collection_name=target_collection,
            filter_builder=filter_builder,
        )

    async def delete_by_document(
        self,
        document_id: str | uuid.UUID,
        collection_name: str | None = None,
    ) -> int:
        """Delete all indexed vectors belonging to a specific document."""
        builder = MetadataFilterBuilder().filter_document(document_id)
        return await self.delete_by_filter(
            filter_builder=builder, collection_name=collection_name
        )

    async def health_check(self) -> dict[str, Any]:
        """Check vector database connection status."""
        return await self._provider.health_check()
