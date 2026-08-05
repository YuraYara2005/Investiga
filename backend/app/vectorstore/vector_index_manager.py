"""Vector Index Manager.

Domain service orchestrating vector index lifecycles, schema verification,
dynamic dimension resolution, collection initialization, aliases, and future re-indexing migrations.
"""

from __future__ import annotations

from app.core.config import VectorStoreSettings
from app.core.logging import get_logger
from app.vectorstore.exceptions import (
    VectorDimensionMismatchException,
)
from app.vectorstore.models import CollectionStats, DistanceMetric
from app.vectorstore.provider import VectorStoreProvider

logger = get_logger(__name__)


class VectorIndexManager:
    """Enterprise manager for vector collections, indexing lifecycle, and schema validation."""

    def __init__(
        self,
        provider: VectorStoreProvider,
        settings: VectorStoreSettings | None = None,
        default_vector_size: int | None = None,
    ) -> None:
        """Initialize VectorIndexManager.

        Args:
            provider: Concrete VectorStoreProvider implementation.
            settings: VectorStoreSettings configuration instance.
            default_vector_size: Optional vector dimension (e.g. derived dynamically from EmbeddingProvider).
        """
        self._provider = provider
        self._settings = settings or VectorStoreSettings()
        # Derive dimension dynamically if provided, otherwise fallback to settings
        self._default_vector_size = default_vector_size or self._settings.vector_size

    @property
    def default_collection_name(self) -> str:
        """Return default collection name from settings."""
        return self._settings.collection_name

    @property
    def default_vector_size(self) -> int:
        """Return effective default vector dimension."""
        return self._default_vector_size

    def set_default_vector_size(self, vector_size: int) -> None:
        """Dynamically update default vector size (e.g., when embedding model loads)."""
        if vector_size <= 0:
            raise ValueError(f"Vector size must be positive, got {vector_size}")
        self._default_vector_size = vector_size

    async def ensure_collection_exists(
        self,
        collection_name: str | None = None,
        vector_size: int | None = None,
        distance: DistanceMetric | None = None,
    ) -> bool:
        """Ensure the specified collection exists; create it if missing."""
        coll_name = collection_name or self.default_collection_name
        size = vector_size or self.default_vector_size
        dist = distance or DistanceMetric(self._settings.distance_metric)

        exists = await self._provider.collection_exists(coll_name)
        if exists:
            # Validate schema
            await self.validate_schema(coll_name, expected_vector_size=size)
            return False

        logger.info(
            "vector_index_creating_missing_collection",
            collection_name=coll_name,
            vector_size=size,
            distance=str(dist),
        )
        created = await self._provider.create_collection(
            collection_name=coll_name,
            vector_size=size,
            distance=dist,
            replication_factor=self._settings.replication_factor,
            write_consistency=self._settings.write_consistency,
        )
        return created

    async def initialize_default_index(self, vector_size: int | None = None) -> bool:
        """Initialize default knowledge collection."""
        return await self.ensure_collection_exists(
            collection_name=self.default_collection_name,
            vector_size=vector_size or self.default_vector_size,
        )

    async def validate_schema(
        self,
        collection_name: str,
        expected_vector_size: int | None = None,
    ) -> bool:
        """Verify that existing collection matches expected vector dimensions."""
        size = expected_vector_size or self.default_vector_size
        stats = await self._provider.get_collection_stats(collection_name)

        if stats.vector_size != size:
            logger.error(
                "vector_schema_dimension_mismatch",
                collection_name=collection_name,
                expected=size,
                actual=stats.vector_size,
            )
            raise VectorDimensionMismatchException(
                expected_dim=size,
                actual_dim=stats.vector_size,
                collection_name=collection_name,
            )

        logger.debug(
            "vector_schema_validated",
            collection_name=collection_name,
            vector_size=stats.vector_size,
            distance=stats.distance,
        )
        return True

    async def delete_index(self, collection_name: str) -> bool:
        """Delete an existing collection index."""
        return await self._provider.delete_collection(collection_name)

    async def get_index_stats(
        self, collection_name: str | None = None
    ) -> CollectionStats:
        """Retrieve diagnostic metrics for a collection."""
        coll_name = collection_name or self.default_collection_name
        return await self._provider.get_collection_stats(coll_name)

    async def reindex_collection(
        self,
        source_collection: str,
        target_collection: str,
        target_vector_size: int | None = None,
        batch_size: int = 100,
    ) -> int:
        """Migrate vector records from source collection to target collection."""
        size = target_vector_size or self.default_vector_size
        await self.ensure_collection_exists(
            collection_name=target_collection,
            vector_size=size,
        )

        from app.vectorstore.filters import MetadataFilterBuilder

        # Scroll all vectors from source collection
        all_records = await self._provider.retrieve_by_filter(
            collection_name=source_collection,
            filter_builder=MetadataFilterBuilder(),
            limit=10000,
            with_vectors=True,
        )

        if not all_records:
            return 0

        upserted = await self._provider.upsert(
            collection_name=target_collection,
            records=all_records,
            batch_size=batch_size,
        )
        logger.info(
            "vector_collection_reindexed",
            source=source_collection,
            target=target_collection,
            total_records=upserted,
        )
        return upserted
