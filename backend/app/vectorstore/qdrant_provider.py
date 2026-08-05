"""Qdrant Vector Store Provider Implementation.

High-performance, asynchronous vector database provider integrating Qdrant
with automatic gRPC-to-HTTP fallback, exponential backoff retry policies,
batch upserts, structured telemetry logging, and robust exception mapping.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from qdrant_client import AsyncQdrantClient, models

from app.core.config import VectorStoreSettings
from app.core.logging import get_logger
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
from app.vectorstore.filters import MetadataFilterBuilder
from app.vectorstore.models import (
    CollectionStats,
    DistanceMetric,
    ScoredVectorRecord,
    VectorRecord,
    VectorSearchResult,
)
from app.vectorstore.provider import VectorStoreProvider

T = TypeVar("T")

logger = get_logger(__name__)

# Mapping from domain DistanceMetric to Qdrant Distance enum
DISTANCE_MAP: dict[DistanceMetric, models.Distance] = {
    DistanceMetric.COSINE: models.Distance.COSINE,
    DistanceMetric.DOT: models.Distance.DOT,
    DistanceMetric.EUCLIDEAN: models.Distance.EUCLID,
    DistanceMetric.MANHATTAN: models.Distance.MANHATTAN,
}


class QdrantProvider(VectorStoreProvider):
    """Production-grade asynchronous Qdrant vector store provider."""

    def __init__(
        self,
        settings: VectorStoreSettings | None = None,
        client: AsyncQdrantClient | None = None,
    ) -> None:
        """Initialize Qdrant provider with settings or pre-configured client.

        Args:
            settings: VectorStoreSettings configuration instance.
            client: Optional injected AsyncQdrantClient (useful for testing).
        """
        self._settings = settings or VectorStoreSettings()
        self._client: AsyncQdrantClient | None = client
        self._is_grpc: bool = self._settings.prefer_grpc
        self._lock = asyncio.Lock()

    @staticmethod
    def _extract_vector(vector_data: Any) -> list[float]:
        """Safely extract float list from Qdrant vector structure."""
        if not vector_data:
            return []
        if isinstance(vector_data, list):
            return [float(v) for v in vector_data if isinstance(v, (int, float))]
        if isinstance(vector_data, dict):
            first_v: Any = next(iter(vector_data.values()), [])
            if isinstance(first_v, list):
                return [float(v) for v in first_v if isinstance(v, (int, float))]
        return []

    async def _get_client(self) -> AsyncQdrantClient:
        """Lazily initialize and return the AsyncQdrantClient instance with gRPC fallback."""
        if self._client is not None:
            return self._client

        async with self._lock:
            if self._client is not None:
                return self._client

            api_key_val = (
                self._settings.api_key.get_secret_value()
                if self._settings.api_key
                else None
            )

            # Attempt preferred gRPC connection
            if self._settings.prefer_grpc:
                try:
                    logger.info(
                        "qdrant_client_connecting_grpc",
                        host=self._settings.host,
                        grpc_port=self._settings.grpc_port,
                    )
                    client = AsyncQdrantClient(
                        host=self._settings.host,
                        port=self._settings.port,
                        grpc_port=self._settings.grpc_port,
                        prefer_grpc=True,
                        https=self._settings.https,
                        api_key=api_key_val,
                        timeout=int(self._settings.timeout),
                    )
                    # Quick connectivity test
                    await client.get_collections()
                    self._client = client
                    self._is_grpc = True
                    logger.info("qdrant_grpc_connection_established")
                    return self._client
                except Exception as exc:
                    logger.warning(
                        "qdrant_grpc_failed_fallback_http",
                        error=str(exc),
                        host=self._settings.host,
                        port=self._settings.port,
                    )

            # Fallback to HTTP/REST
            try:
                logger.info(
                    "qdrant_client_connecting_http",
                    host=self._settings.host,
                    port=self._settings.port,
                )
                client = AsyncQdrantClient(
                    host=self._settings.host,
                    port=self._settings.port,
                    prefer_grpc=False,
                    https=self._settings.https,
                    api_key=api_key_val,
                    timeout=int(self._settings.timeout),
                )
                self._client = client
                self._is_grpc = False
                logger.info("qdrant_http_connection_established")
                return self._client
            except Exception as exc:
                logger.error("qdrant_connection_failed", error=str(exc))
                raise VectorStoreConnectionException(
                    message=f"Failed to connect to Qdrant at {self._settings.host}:{self._settings.port}: {exc}",
                    host=self._settings.host,
                    port=self._settings.port,
                ) from exc

    async def _execute_with_retry(
        self, operation_name: str, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """Execute a Qdrant operation with exponential backoff on transient errors."""
        max_retries = self._settings.max_retries
        base_delay = 0.2
        last_exception: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except (
                CollectionNotFoundException,
                CollectionAlreadyExistsException,
                VectorDimensionMismatchException,
                InvalidFilterException,
            ):
                # Non-retryable domain exceptions
                raise
            except Exception as exc:
                last_exception = exc
                if attempt < max_retries:
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        "qdrant_operation_retry",
                        operation=operation_name,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay_seconds=delay,
                        error=str(exc),
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "qdrant_operation_failed_after_retries",
                        operation=operation_name,
                        attempts=attempt + 1,
                        error=str(exc),
                    )

        raise (
            last_exception
            if last_exception
            else VectorStoreException(f"Operation {operation_name} failed.")
        )

    # -----------------------------------------------------------------------
    # Collection Lifecycle Management
    # -----------------------------------------------------------------------

    async def create_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: DistanceMetric = DistanceMetric.COSINE,
        replication_factor: int = 1,
        write_consistency: str = "majority",
    ) -> bool:
        """Create a new vector collection in Qdrant."""
        client = await self._get_client()
        distance_qdrant = DISTANCE_MAP.get(distance, models.Distance.COSINE)

        async def _create() -> bool:
            exists = await client.collection_exists(collection_name=collection_name)
            if exists:
                raise CollectionAlreadyExistsException(collection_name)

            vectors_config = models.VectorParams(
                size=vector_size,
                distance=distance_qdrant,
            )
            created = await client.create_collection(
                collection_name=collection_name,
                vectors_config=vectors_config,
                replication_factor=replication_factor,
            )
            logger.info(
                "qdrant_collection_created",
                collection_name=collection_name,
                vector_size=vector_size,
                distance=str(distance),
            )
            return bool(created)

        try:
            return bool(await self._execute_with_retry("create_collection", _create))
        except CollectionAlreadyExistsException:
            raise
        except Exception as exc:
            raise VectorStoreException(
                f"Failed to create collection '{collection_name}': {exc}"
            ) from exc

    async def delete_collection(self, collection_name: str) -> bool:
        """Delete an existing collection in Qdrant."""
        client = await self._get_client()

        async def _delete() -> bool:
            exists = await client.collection_exists(collection_name=collection_name)
            if not exists:
                raise CollectionNotFoundException(collection_name)

            deleted = await client.delete_collection(collection_name=collection_name)
            logger.info("qdrant_collection_deleted", collection_name=collection_name)
            return bool(deleted)

        try:
            return bool(await self._execute_with_retry("delete_collection", _delete))
        except CollectionNotFoundException:
            raise
        except Exception as exc:
            raise VectorStoreException(
                f"Failed to delete collection '{collection_name}': {exc}"
            ) from exc

    async def recreate_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: DistanceMetric = DistanceMetric.COSINE,
        replication_factor: int = 1,
        write_consistency: str = "majority",
    ) -> bool:
        """Recreate a collection, dropping existing points if the collection already exists."""
        client = await self._get_client()
        distance_qdrant = DISTANCE_MAP.get(distance, models.Distance.COSINE)

        async def _recreate() -> bool:
            vectors_config = models.VectorParams(
                size=vector_size,
                distance=distance_qdrant,
            )
            exists = await client.collection_exists(collection_name=collection_name)
            if exists:
                await client.delete_collection(collection_name=collection_name)

            created = await client.create_collection(
                collection_name=collection_name,
                vectors_config=vectors_config,
                replication_factor=replication_factor,
            )
            logger.info(
                "qdrant_collection_recreated",
                collection_name=collection_name,
                vector_size=vector_size,
                distance=str(distance),
            )
            return bool(created)

        try:
            return bool(
                await self._execute_with_retry("recreate_collection", _recreate)
            )
        except Exception as exc:
            raise VectorStoreException(
                f"Failed to recreate collection '{collection_name}': {exc}"
            ) from exc

    async def collection_exists(self, collection_name: str) -> bool:
        """Check if collection exists."""
        client = await self._get_client()

        async def _exists() -> bool:
            return bool(await client.collection_exists(collection_name=collection_name))

        return bool(await self._execute_with_retry("collection_exists", _exists))

    async def get_collection_stats(self, collection_name: str) -> CollectionStats:
        """Retrieve diagnostic counts and status metrics for a collection."""
        client = await self._get_client()

        async def _get_stats() -> CollectionStats:
            exists = await client.collection_exists(collection_name=collection_name)
            if not exists:
                raise CollectionNotFoundException(collection_name)

            info = await client.get_collection(collection_name=collection_name)

            # Safely extract vector params
            vector_size = self._settings.vector_size
            distance_str = self._settings.distance_metric

            if info.config and info.config.params and info.config.params.vectors:
                vectors_cfg = info.config.params.vectors
                if isinstance(vectors_cfg, models.VectorParams):
                    vector_size = vectors_cfg.size
                    distance_str = str(vectors_cfg.distance).lower()
                elif isinstance(vectors_cfg, dict):
                    # Multi-vector config or dict
                    first_cfg = next(iter(vectors_cfg.values()), None)
                    if isinstance(first_cfg, models.VectorParams):
                        vector_size = first_cfg.size
                        distance_str = str(first_cfg.distance).lower()

            vectors_cnt = (
                getattr(info, "vectors_count", getattr(info, "points_count", 0)) or 0
            )

            return CollectionStats(
                collection_name=collection_name,
                status=str(info.status),
                vectors_count=vectors_cnt,
                indexed_vectors_count=info.indexed_vectors_count or 0,
                points_count=info.points_count or 0,
                segments_count=info.segments_count or 0,
                vector_size=vector_size,
                distance=distance_str,
            )

        try:
            return await self._execute_with_retry("get_collection_stats", _get_stats)
        except CollectionNotFoundException:
            raise
        except Exception as exc:
            raise VectorStoreException(
                f"Failed to retrieve stats for '{collection_name}': {exc}"
            ) from exc

    # -----------------------------------------------------------------------
    # Vector CRUD & Batch Operations
    # -----------------------------------------------------------------------

    async def upsert(
        self,
        collection_name: str,
        records: list[VectorRecord],
        batch_size: int = 100,
    ) -> int:
        """Insert or update a list of vector records in batches."""
        if not records:
            return 0

        client = await self._get_client()
        effective_batch_size = max(1, min(batch_size, self._settings.batch_size))
        total_upserted = 0

        # Validate existence
        exists = await client.collection_exists(collection_name=collection_name)
        if not exists:
            raise CollectionNotFoundException(collection_name)

        async def _upsert_batch(batch_points: list[models.PointStruct]) -> None:
            await client.upsert(
                collection_name=collection_name,
                points=batch_points,
                wait=True,
            )

        for i in range(0, len(records), effective_batch_size):
            chunk = records[i : i + effective_batch_size]
            points: list[models.PointStruct] = []

            for rec in chunk:
                # Convert ID to str or valid UUID for Qdrant
                pid = str(rec.id)
                points.append(
                    models.PointStruct(
                        id=pid,
                        vector=rec.vector,
                        payload=rec.payload_dict,
                    )
                )

            try:
                await self._execute_with_retry("upsert_batch", _upsert_batch, points)
                total_upserted += len(points)
            except Exception as exc:
                raise VectorUpsertException(
                    collection_name=collection_name,
                    record_count=len(chunk),
                    reason=str(exc),
                ) from exc

        logger.info(
            "qdrant_vectors_upserted",
            collection_name=collection_name,
            total_records=total_upserted,
        )
        return total_upserted

    async def delete(
        self,
        collection_name: str,
        point_ids: Sequence[str | uuid.UUID],
    ) -> int:
        """Delete specific vector points by ID."""
        if not point_ids:
            return 0

        client = await self._get_client()
        str_ids = [str(pid) for pid in point_ids]

        async def _delete() -> int:
            exists = await client.collection_exists(collection_name=collection_name)
            if not exists:
                raise CollectionNotFoundException(collection_name)

            await client.delete(
                collection_name=collection_name,
                points_selector=models.PointIdsList(points=str_ids),
                wait=True,
            )
            return len(str_ids)

        try:
            res = await self._execute_with_retry("delete_points", _delete)
            logger.info(
                "qdrant_points_deleted", collection_name=collection_name, count=res
            )
            return int(res)
        except CollectionNotFoundException:
            raise
        except Exception as exc:
            raise VectorDeleteException(
                collection_name=collection_name, reason=str(exc)
            ) from exc

    async def delete_by_filter(
        self,
        collection_name: str,
        filter_builder: MetadataFilterBuilder,
    ) -> int:
        """Delete points matching the metadata filter."""
        client = await self._get_client()
        qdrant_filter = filter_builder.to_qdrant_filter()

        if qdrant_filter is None:
            raise InvalidFilterException(
                "Cannot delete by empty filter: specify at least one filter criterion."
            )

        async def _delete_filtered() -> int:
            exists = await client.collection_exists(collection_name=collection_name)
            if not exists:
                raise CollectionNotFoundException(collection_name)

            await client.delete(
                collection_name=collection_name,
                points_selector=models.FilterSelector(filter=qdrant_filter),
                wait=True,
            )
            return 1

        try:
            await self._execute_with_retry("delete_by_filter", _delete_filtered)
            logger.info(
                "qdrant_points_deleted_by_filter", collection_name=collection_name
            )
            return 1
        except (CollectionNotFoundException, InvalidFilterException):
            raise
        except Exception as exc:
            raise VectorDeleteException(
                collection_name=collection_name, reason=str(exc)
            ) from exc

    async def retrieve_by_ids(
        self,
        collection_name: str,
        point_ids: Sequence[str | uuid.UUID],
        with_vectors: bool = False,
    ) -> list[VectorRecord]:
        """Retrieve vector points by their unique IDs."""
        if not point_ids:
            return []

        client = await self._get_client()
        str_ids = [str(pid) for pid in point_ids]

        async def _retrieve() -> list[VectorRecord]:
            exists = await client.collection_exists(collection_name=collection_name)
            if not exists:
                raise CollectionNotFoundException(collection_name)

            records = await client.retrieve(
                collection_name=collection_name,
                ids=str_ids,
                with_payload=True,
                with_vectors=with_vectors,
            )
            result: list[VectorRecord] = []
            for r in records:
                vec: list[float] = (
                    self._extract_vector(r.vector) if with_vectors else []
                )
                result.append(
                    VectorRecord(
                        id=str(r.id),
                        vector=vec,
                        payload=r.payload or {},
                    )
                )
            return result

        try:
            return await self._execute_with_retry("retrieve_by_ids", _retrieve)
        except CollectionNotFoundException:
            raise
        except Exception as exc:
            raise VectorQueryException(
                collection_name=collection_name, reason=str(exc)
            ) from exc

    async def retrieve_by_filter(
        self,
        collection_name: str,
        filter_builder: MetadataFilterBuilder,
        limit: int = 100,
        offset: int = 0,
        with_vectors: bool = False,
    ) -> list[VectorRecord]:
        """Retrieve vector records matching metadata filter criteria."""
        client = await self._get_client()
        qdrant_filter = filter_builder.to_qdrant_filter()

        async def _scroll() -> list[VectorRecord]:
            exists = await client.collection_exists(collection_name=collection_name)
            if not exists:
                raise CollectionNotFoundException(collection_name)

            scroll_result, _ = await client.scroll(
                collection_name=collection_name,
                scroll_filter=qdrant_filter,
                limit=limit,
                offset=offset or None,
                with_payload=True,
                with_vectors=with_vectors,
            )
            result: list[VectorRecord] = []
            for r in scroll_result:
                vec: list[float] = (
                    self._extract_vector(r.vector) if with_vectors else []
                )
                result.append(
                    VectorRecord(
                        id=str(r.id),
                        vector=vec,
                        payload=r.payload or {},
                    )
                )
            return result

        try:
            return await self._execute_with_retry("retrieve_by_filter", _scroll)
        except CollectionNotFoundException:
            raise
        except Exception as exc:
            raise VectorQueryException(
                collection_name=collection_name, reason=str(exc)
            ) from exc

    # -----------------------------------------------------------------------
    # Similarity Search
    # -----------------------------------------------------------------------

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: float | None = None,
        filter_builder: MetadataFilterBuilder | None = None,
        with_vectors: bool = False,
    ) -> VectorSearchResult:
        """Perform nearest-neighbor vector similarity search."""
        if not query_vector:
            raise VectorQueryException(
                collection_name=collection_name, reason="Query vector cannot be empty."
            )

        client = await self._get_client()
        qdrant_filter = filter_builder.to_qdrant_filter() if filter_builder else None
        start_time = time.perf_counter()

        async def _search() -> list[Any]:
            exists = await client.collection_exists(collection_name=collection_name)
            if not exists:
                raise CollectionNotFoundException(collection_name)

            if hasattr(client, "query_points"):
                response = await client.query_points(
                    collection_name=collection_name,
                    query=query_vector,
                    query_filter=qdrant_filter,
                    limit=limit,
                    score_threshold=score_threshold,
                    with_payload=True,
                    with_vectors=with_vectors,
                )
                return getattr(response, "points", [])
            elif hasattr(client, "search"):
                return await client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    query_filter=qdrant_filter,
                    limit=limit,
                    score_threshold=score_threshold,
                    with_payload=True,
                    with_vectors=with_vectors,
                )
            return []

        try:
            scored_points = await self._execute_with_retry("search", _search)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            records: list[ScoredVectorRecord] = []
            for pt in scored_points:
                vec: list[float] | None = (
                    self._extract_vector(pt.vector) if with_vectors else None
                )
                records.append(
                    ScoredVectorRecord(
                        id=str(pt.id),
                        score=float(pt.score),
                        vector=vec,
                        payload=pt.payload or {},
                    )
                )

            logger.info(
                "qdrant_search_completed",
                collection_name=collection_name,
                found_count=len(records),
                latency_ms=round(elapsed_ms, 2),
            )

            return VectorSearchResult(
                collection_name=collection_name,
                query_vector_dim=len(query_vector),
                results=records,
                total_found=len(records),
                latency_ms=elapsed_ms,
                metadata={
                    "score_threshold": score_threshold,
                    "transport": "grpc" if self._is_grpc else "http",
                },
            )
        except CollectionNotFoundException:
            raise
        except Exception as exc:
            raise VectorQueryException(
                collection_name=collection_name, reason=str(exc)
            ) from exc

    # -----------------------------------------------------------------------
    # Health Check & Graceful Shutdown
    # -----------------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """Perform health and connectivity diagnostics."""
        start_time = time.perf_counter()
        try:
            client = await self._get_client()
            collections_res = await client.get_collections()
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            return {
                "status": "healthy",
                "provider": "QdrantProvider",
                "transport": "grpc" if self._is_grpc else "http",
                "host": self._settings.host,
                "port": self._settings.port,
                "grpc_port": self._settings.grpc_port,
                "collections_count": len(collections_res.collections),
                "latency_ms": round(latency_ms, 2),
            }
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return {
                "status": "unhealthy",
                "provider": "QdrantProvider",
                "error": str(exc),
                "host": self._settings.host,
                "port": self._settings.port,
                "latency_ms": round(latency_ms, 2),
            }

    async def close(self) -> None:
        """Close client connections gracefully."""
        if self._client is not None:
            try:
                await self._client.close()
                logger.info("qdrant_client_closed")
            except Exception as exc:
                logger.warning("qdrant_client_close_error", error=str(exc))
            finally:
                self._client = None
