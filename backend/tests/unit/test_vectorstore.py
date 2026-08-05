"""Unit tests for Vector Database Infrastructure Subsystem.

Covers:
- VectorPayload multi-tenancy, rich metadata, hybrid search fields, and serialization
- VectorRecord, ScoredVectorRecord, CollectionStats, and VectorSearchResult models
- MetadataFilterBuilder DSL rules, logical combinations, and Qdrant filter translation
- VectorStoreProvider abstract interface and MockVectorStoreProvider
- QdrantProvider operations (collection lifecycle, batch upserts, similarity search,
  retrieval, filtering, deletion, health checks, gRPC fallback, and retry policies)
- VectorIndexManager schema verification, dynamic dimensioning, and re-indexing
- VectorRepository domain-agnostic vector persistence and query workflows
- VectorStoreSettings configuration and root Settings integration
- Exception hierarchy, status codes, and error payloads
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from qdrant_client import models

from app.core.config import VectorStoreSettings, get_settings
from app.vectorstore.exceptions import (
    CollectionAlreadyExistsException,
    CollectionNotFoundException,
    InvalidFilterException,
    VectorDimensionMismatchException,
    VectorStoreConnectionException,
    VectorUpsertException,
)
from app.vectorstore.filters import MetadataFilterBuilder
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

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_payload() -> VectorPayload:
    """Fixture providing a rich, multi-tenant VectorPayload."""
    return VectorPayload(
        tenant_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        visibility="workspace",
        document_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        chunk_index=0,
        document_version=2,
        source="knowledge_upload",
        source_type="file",
        file_name="incident_sop_2026.pdf",
        title="Incident Response Standard Operating Procedure",
        category="security_ops",
        mime_type="application/pdf",
        checksum="a1b2c3d4e5f67890",
        page_number=3,
        heading="Triage & Containment",
        tags=["security", "sop", "incident"],
        created_by=uuid.uuid4(),
        language="en",
        word_count=120,
        character_count=850,
        token_count=180,
        processing_version="1.2.0",
        parser_version="1.1.0",
        chunk_strategy="adaptive",
        embedding_model="BAAI/bge-base-en-v1.5",
        embedding_provider="SentenceTransformerProvider",
        embedding_dimension=768,
        raw_text="Isolate compromised endpoints immediately and preserve volatile memory.",
        normalized_text="isolate compromised endpoints immediately and preserve volatile memory",
        keywords=["isolate", "compromised", "endpoints", "volatile", "memory"],
        extra={"incident_severity": "critical"},
    )


@pytest.fixture
def sample_vector_records(sample_payload: VectorPayload) -> list[VectorRecord]:
    """Fixture providing a list of VectorRecord objects."""
    records: list[VectorRecord] = []
    for i in range(5):
        payload = sample_payload.model_copy()
        payload.chunk_index = i
        payload.chunk_id = uuid.uuid4()
        records.append(
            VectorRecord(
                id=str(payload.chunk_id),
                vector=[0.1 * (i + 1)] * 768,
                payload=payload,
            )
        )
    return records


class MockVectorStoreProvider(VectorStoreProvider):
    """In-memory mock vector store provider for interface validation."""

    def __init__(self) -> None:
        self.collections: dict[str, dict[str, Any]] = {}
        self.points: dict[str, dict[str, VectorRecord]] = {}

    async def create_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: DistanceMetric = DistanceMetric.COSINE,
        replication_factor: int = 1,
        write_consistency: str = "majority",
    ) -> bool:
        if collection_name in self.collections:
            raise CollectionAlreadyExistsException(collection_name)
        self.collections[collection_name] = {
            "vector_size": vector_size,
            "distance": distance.value,
        }
        self.points[collection_name] = {}
        return True

    async def delete_collection(self, collection_name: str) -> bool:
        if collection_name not in self.collections:
            raise CollectionNotFoundException(collection_name)
        del self.collections[collection_name]
        del self.points[collection_name]
        return True

    async def recreate_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: DistanceMetric = DistanceMetric.COSINE,
        replication_factor: int = 1,
        write_consistency: str = "majority",
    ) -> bool:
        self.collections[collection_name] = {
            "vector_size": vector_size,
            "distance": distance.value,
        }
        self.points[collection_name] = {}
        return True

    async def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.collections

    async def get_collection_stats(self, collection_name: str) -> CollectionStats:
        if collection_name not in self.collections:
            raise CollectionNotFoundException(collection_name)
        cfg = self.collections[collection_name]
        pts = self.points.get(collection_name, {})
        return CollectionStats(
            collection_name=collection_name,
            status="green",
            vectors_count=len(pts),
            indexed_vectors_count=len(pts),
            points_count=len(pts),
            segments_count=1,
            vector_size=cfg["vector_size"],
            distance=cfg["distance"],
        )

    async def upsert(
        self,
        collection_name: str,
        records: list[VectorRecord],
        batch_size: int = 100,
    ) -> int:
        if collection_name not in self.collections:
            raise CollectionNotFoundException(collection_name)
        for rec in records:
            self.points[collection_name][rec.id_str] = rec
        return len(records)

    async def delete(
        self,
        collection_name: str,
        point_ids: Sequence[str | uuid.UUID],
    ) -> int:
        if collection_name not in self.collections:
            raise CollectionNotFoundException(collection_name)
        count = 0
        for pid in point_ids:
            if str(pid) in self.points[collection_name]:
                del self.points[collection_name][str(pid)]
                count += 1
        return count

    async def delete_by_filter(
        self,
        collection_name: str,
        filter_builder: MetadataFilterBuilder,
    ) -> int:
        if collection_name not in self.collections:
            raise CollectionNotFoundException(collection_name)
        # Mock simple document_id deletion
        filt = filter_builder.to_dict()
        doc_id = None
        for m in filt.get("must", []):
            if m.get("key") == "document_id":
                doc_id = m.get("value")
        count = 0
        to_del = []
        for pid, rec in self.points[collection_name].items():
            payload = rec.payload_dict
            if doc_id and str(payload.get("document_id")) == str(doc_id):
                to_del.append(pid)
        for pid in to_del:
            del self.points[collection_name][pid]
            count += 1
        return count

    async def retrieve_by_ids(
        self,
        collection_name: str,
        point_ids: Sequence[str | uuid.UUID],
        with_vectors: bool = False,
    ) -> list[VectorRecord]:
        if collection_name not in self.collections:
            raise CollectionNotFoundException(collection_name)
        res = []
        for pid in point_ids:
            if str(pid) in self.points[collection_name]:
                res.append(self.points[collection_name][str(pid)])
        return res

    async def retrieve_by_filter(
        self,
        collection_name: str,
        filter_builder: MetadataFilterBuilder,
        limit: int = 100,
        offset: int = 0,
        with_vectors: bool = False,
    ) -> list[VectorRecord]:
        if collection_name not in self.collections:
            raise CollectionNotFoundException(collection_name)
        all_pts = list(self.points[collection_name].values())
        return all_pts[offset : offset + limit]

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: float | None = None,
        filter_builder: MetadataFilterBuilder | None = None,
        with_vectors: bool = False,
    ) -> VectorSearchResult:
        if collection_name not in self.collections:
            raise CollectionNotFoundException(collection_name)
        results: list[ScoredVectorRecord] = []
        for pid, rec in list(self.points[collection_name].items())[:limit]:
            results.append(
                ScoredVectorRecord(
                    id=pid,
                    score=0.95,
                    vector=rec.vector if with_vectors else None,
                    payload=rec.payload,
                )
            )
        return VectorSearchResult(
            collection_name=collection_name,
            query_vector_dim=len(query_vector),
            results=results,
            total_found=len(results),
            latency_ms=1.5,
        )

    async def health_check(self) -> dict[str, Any]:
        return {"status": "healthy", "provider": "MockVectorStoreProvider"}

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# 1. Models & Schemas Unit Tests
# ---------------------------------------------------------------------------


def test_vector_payload_model(sample_payload: VectorPayload) -> None:
    """Verify VectorPayload instantiation, validation, multi-tenancy, and serialization."""
    assert sample_payload.tenant_id is not None
    assert sample_payload.visibility == "workspace"
    assert sample_payload.document_version == 2
    assert sample_payload.chunk_strategy == "adaptive"
    assert sample_payload.embedding_dimension == 768
    assert sample_payload.raw_text is not None
    assert "endpoints" in sample_payload.keywords

    data = sample_payload.to_dict()
    assert isinstance(data["tenant_id"], str)
    assert isinstance(data["document_id"], str)
    assert isinstance(data["chunk_id"], str)
    assert data["extra"]["incident_severity"] == "critical"


def test_vector_record_properties(sample_payload: VectorPayload) -> None:
    """Verify VectorRecord properties and string conversions."""
    pid = uuid.uuid4()
    record = VectorRecord(
        id=pid,
        vector=[0.5] * 768,
        payload=sample_payload,
    )
    assert record.id_str == str(pid)
    assert isinstance(record.payload_dict, dict)
    assert record.payload_dict["file_name"] == "incident_sop_2026.pdf"


def test_scored_vector_record_properties() -> None:
    """Verify ScoredVectorRecord scoring and properties."""
    pid = uuid.uuid4()
    record = ScoredVectorRecord(
        id=pid,
        score=0.925,
        vector=[0.1, 0.2, 0.3],
        payload={"category": "ops"},
    )
    assert record.id_str == str(pid)
    assert record.score == 0.925
    assert record.vector == [0.1, 0.2, 0.3]


def test_collection_stats_model() -> None:
    """Verify CollectionStats serialization and field validations."""
    stats = CollectionStats(
        collection_name="investiga_knowledge",
        status="green",
        vectors_count=1000,
        indexed_vectors_count=980,
        points_count=1000,
        segments_count=4,
        vector_size=768,
        distance="cosine",
    )
    assert stats.collection_name == "investiga_knowledge"
    assert stats.vectors_count == 1000
    assert stats.vector_size == 768


def test_vector_search_result_model() -> None:
    """Verify VectorSearchResult container and telemetry."""
    res = VectorSearchResult(
        collection_name="test_col",
        query_vector_dim=768,
        results=[],
        total_found=0,
        latency_ms=3.4,
    )
    assert res.latency_ms == 3.4
    assert res.total_found == 0


# ---------------------------------------------------------------------------
# 2. MetadataFilterBuilder Unit Tests
# ---------------------------------------------------------------------------


def test_filter_builder_must_should_must_not() -> None:
    """Verify basic fluent filter clauses."""
    builder = (
        MetadataFilterBuilder()
        .must("tenant_id", "tenant-1")
        .should("category", "security")
        .must_not("visibility", "private")
    )
    assert builder.is_empty() is False
    d = builder.to_dict()
    assert len(d["must"]) == 1
    assert len(d["should"]) == 1
    assert len(d["must_not"]) == 1
    assert d["must"][0]["key"] == "tenant_id"
    assert d["must"][0]["value"] == "tenant-1"


def test_filter_builder_in_range_match() -> None:
    """Verify filter_in, filter_range, and filter_match clauses."""
    builder = (
        MetadataFilterBuilder()
        .filter_in("tags", ["sop", "ops"])
        .filter_range("page_number", gte=1, lte=10)
        .filter_match("heading", "Containment")
    )
    d = builder.to_dict()
    assert len(d["must"]) == 3
    assert d["must"][0]["op"] == "in"
    assert d["must"][0]["value"] == ["sop", "ops"]
    assert d["must"][1]["op"] == "range"
    assert d["must"][1]["extra"] == {"gte": 1, "lte": 10}
    assert d["must"][2]["op"] == "match_text"
    assert d["must"][2]["value"] == "Containment"


def test_filter_builder_convenience_methods() -> None:
    """Verify filter_tenant, filter_workspace, filter_document."""
    t_id = uuid.uuid4()
    w_id = uuid.uuid4()
    d_id = uuid.uuid4()

    builder = (
        MetadataFilterBuilder()
        .filter_tenant(t_id)
        .filter_workspace(w_id)
        .filter_document(d_id)
    )
    d = builder.to_dict()
    assert len(d["must"]) == 3
    assert d["must"][0]["value"] == str(t_id)
    assert d["must"][1]["value"] == str(w_id)
    assert d["must"][2]["value"] == str(d_id)


def test_filter_builder_invalid_inputs() -> None:
    """Verify InvalidFilterException for empty keys or parameters."""
    with pytest.raises(InvalidFilterException):
        MetadataFilterBuilder().must("  ", "value")

    with pytest.raises(InvalidFilterException):
        MetadataFilterBuilder().filter_in("key", [])

    with pytest.raises(InvalidFilterException):
        MetadataFilterBuilder().filter_range("key")

    with pytest.raises(InvalidFilterException):
        MetadataFilterBuilder().filter_match("key", "   ")


def test_filter_builder_to_from_dict() -> None:
    """Verify round-trip serialization between builder and dictionary."""
    orig = (
        MetadataFilterBuilder()
        .must("tenant_id", "t-123")
        .filter_in("tags", ["a", "b"])
        .filter_range("page", gte=2)
        .filter_match("text", "incident")
        .should("source", "upload")
        .must_not("deleted", True)
    )
    d = orig.to_dict()
    restored = MetadataFilterBuilder.from_dict(d)
    assert restored.to_dict() == d


def test_filter_builder_to_qdrant_filter() -> None:
    """Verify conversion to Qdrant models.Filter object."""
    builder = (
        MetadataFilterBuilder()
        .must("tenant_id", "tenant-1")
        .filter_in("tags", ["a", "b"])
        .filter_range("page_number", gte=1)
        .filter_match("heading", "triage")
        .should("category", "ops")
        .must_not("visibility", "archived")
    )
    q_filter = builder.to_qdrant_filter()
    assert isinstance(q_filter, models.Filter)
    assert isinstance(q_filter.must, list)
    assert len(q_filter.must) == 4
    assert isinstance(q_filter.should, list)
    assert len(q_filter.should) == 1
    assert isinstance(q_filter.must_not, list)
    assert len(q_filter.must_not) == 1


def test_filter_builder_empty_returns_none() -> None:
    """Empty filter builder returns None for Qdrant filter."""
    builder = MetadataFilterBuilder()
    assert builder.to_qdrant_filter() is None


# ---------------------------------------------------------------------------
# 3. QdrantProvider Unit Tests (with Mocked AsyncQdrantClient)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_qdrant_provider_create_collection_success() -> None:
    """Verify collection creation executes with appropriate vector params."""
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = False
    mock_client.create_collection.return_value = True

    provider = QdrantProvider(client=mock_client)
    res = await provider.create_collection(
        collection_name="new_collection",
        vector_size=768,
        distance=DistanceMetric.COSINE,
    )
    assert res is True
    mock_client.create_collection.assert_called_once()
    call_args = mock_client.create_collection.call_args.kwargs
    assert call_args["collection_name"] == "new_collection"
    assert call_args["vectors_config"].size == 768
    assert call_args["vectors_config"].distance == models.Distance.COSINE


@pytest.mark.asyncio
async def test_qdrant_provider_create_collection_already_exists() -> None:
    """Verify CollectionAlreadyExistsException when collection already exists."""
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = True

    provider = QdrantProvider(client=mock_client)
    with pytest.raises(CollectionAlreadyExistsException):
        await provider.create_collection(
            collection_name="existing_collection", vector_size=768
        )


@pytest.mark.asyncio
async def test_qdrant_provider_delete_collection() -> None:
    """Verify delete collection calls client."""
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = True
    mock_client.delete_collection.return_value = True

    provider = QdrantProvider(client=mock_client)
    res = await provider.delete_collection("target_collection")
    assert res is True
    mock_client.delete_collection.assert_called_once_with(
        collection_name="target_collection"
    )


@pytest.mark.asyncio
async def test_qdrant_provider_delete_collection_not_found() -> None:
    """Verify CollectionNotFoundException when deleting non-existent collection."""
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = False

    provider = QdrantProvider(client=mock_client)
    with pytest.raises(CollectionNotFoundException):
        await provider.delete_collection("missing_collection")


@pytest.mark.asyncio
async def test_qdrant_provider_recreate_collection() -> None:
    """Verify recreate collection deletes existing if present and creates new."""
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = True
    mock_client.delete_collection.return_value = True
    mock_client.create_collection.return_value = True

    provider = QdrantProvider(client=mock_client)
    res = await provider.recreate_collection(
        collection_name="recreated_collection",
        vector_size=384,
        distance=DistanceMetric.DOT,
    )
    assert res is True
    mock_client.delete_collection.assert_called_once_with(
        collection_name="recreated_collection"
    )
    mock_client.create_collection.assert_called_once()


@pytest.mark.asyncio
async def test_qdrant_provider_get_collection_stats() -> None:
    """Verify collection stats extraction."""
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = True

    mock_info = MagicMock()
    mock_info.status = "green"
    mock_info.vectors_count = 500
    mock_info.indexed_vectors_count = 500
    mock_info.points_count = 500
    mock_info.segments_count = 2
    mock_info.config.params.vectors = models.VectorParams(
        size=768, distance=models.Distance.COSINE
    )
    mock_client.get_collection.return_value = mock_info

    provider = QdrantProvider(client=mock_client)
    stats = await provider.get_collection_stats("stats_collection")

    assert stats.collection_name == "stats_collection"
    assert stats.vectors_count == 500
    assert stats.vector_size == 768
    assert stats.status == "green"


@pytest.mark.asyncio
async def test_qdrant_provider_upsert_batches(
    sample_vector_records: list[VectorRecord],
) -> None:
    """Verify batch upserts batching logic."""
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = True
    mock_client.upsert.return_value = MagicMock(status="completed")

    provider = QdrantProvider(client=mock_client)
    # Upsert 5 records with batch size 2 -> 3 batch calls
    count = await provider.upsert("batch_col", sample_vector_records, batch_size=2)

    assert count == len(sample_vector_records)
    assert mock_client.upsert.call_count == 3


@pytest.mark.asyncio
async def test_qdrant_provider_upsert_empty_list() -> None:
    """Empty list returns 0 without calling backend."""
    mock_client = AsyncMock()
    provider = QdrantProvider(client=mock_client)
    count = await provider.upsert("any_col", [])
    assert count == 0
    mock_client.upsert.assert_not_called()


@pytest.mark.asyncio
async def test_qdrant_provider_upsert_collection_not_found(
    sample_vector_records: list[VectorRecord],
) -> None:
    """Upserting to non-existent collection raises CollectionNotFoundException."""
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = False

    provider = QdrantProvider(client=mock_client)
    with pytest.raises(CollectionNotFoundException):
        await provider.upsert("missing_col", sample_vector_records)


@pytest.mark.asyncio
async def test_qdrant_provider_delete_points() -> None:
    """Verify deletion by point IDs."""
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = True
    mock_client.delete.return_value = MagicMock(status="completed")

    provider = QdrantProvider(client=mock_client)
    ids: list[str | uuid.UUID] = [uuid.uuid4(), uuid.uuid4()]
    count = await provider.delete("del_col", ids)

    assert count == 2
    mock_client.delete.assert_called_once()


@pytest.mark.asyncio
async def test_qdrant_provider_delete_by_filter() -> None:
    """Verify deletion by metadata filter."""
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = True
    mock_client.delete.return_value = MagicMock(status="completed")

    provider = QdrantProvider(client=mock_client)
    builder = MetadataFilterBuilder().filter_document(uuid.uuid4())
    count = await provider.delete_by_filter("filter_del_col", builder)

    assert count == 1
    mock_client.delete.assert_called_once()


@pytest.mark.asyncio
async def test_qdrant_provider_retrieve_by_ids() -> None:
    """Verify retrieve by IDs mapping."""
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = True

    rec_mock = MagicMock()
    rec_mock.id = "p-1"
    rec_mock.vector = [0.1, 0.2]
    rec_mock.payload = {"category": "security"}
    mock_client.retrieve.return_value = [rec_mock]

    provider = QdrantProvider(client=mock_client)
    records = await provider.retrieve_by_ids("ret_col", ["p-1"], with_vectors=True)

    assert len(records) == 1
    assert records[0].id == "p-1"
    assert records[0].vector == [0.1, 0.2]
    assert records[0].payload_dict["category"] == "security"


@pytest.mark.asyncio
async def test_qdrant_provider_search() -> None:
    """Verify search returns ScoredVectorRecord list with latency."""
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = True

    scored_pt = MagicMock()
    scored_pt.id = "match-1"
    scored_pt.score = 0.94
    scored_pt.vector = [0.1] * 768
    scored_pt.payload = {"title": "Incident SOP"}
    mock_client.query_points.return_value = MagicMock(points=[scored_pt])

    provider = QdrantProvider(client=mock_client)
    filter_b = MetadataFilterBuilder().must("category", "ops")
    res = await provider.search(
        collection_name="search_col",
        query_vector=[0.1] * 768,
        limit=5,
        score_threshold=0.8,
        filter_builder=filter_b,
        with_vectors=True,
    )

    assert isinstance(res, VectorSearchResult)
    assert res.total_found == 1
    assert res.results[0].id == "match-1"
    assert res.results[0].score == 0.94
    assert res.results[0].payload_dict["title"] == "Incident SOP"
    assert res.latency_ms >= 0.0


@pytest.mark.asyncio
async def test_qdrant_provider_health_check_healthy() -> None:
    """Verify health_check response when backend is healthy."""
    mock_client = AsyncMock()
    mock_colls = MagicMock()
    mock_colls.collections = [MagicMock(), MagicMock()]
    mock_client.get_collections.return_value = mock_colls

    provider = QdrantProvider(client=mock_client)
    health = await provider.health_check()

    assert health["status"] == "healthy"
    assert health["collections_count"] == 2
    assert health["provider"] == "QdrantProvider"


@pytest.mark.asyncio
async def test_qdrant_provider_health_check_unhealthy() -> None:
    """Verify health_check response when backend raises connection error."""
    mock_client = AsyncMock()
    mock_client.get_collections.side_effect = ConnectionRefusedError(
        "Connection refused"
    )

    provider = QdrantProvider(client=mock_client)
    health = await provider.health_check()

    assert health["status"] == "unhealthy"
    assert "Connection refused" in health["error"]


@pytest.mark.asyncio
async def test_qdrant_provider_retry_mechanism() -> None:
    """Verify retry policy executes on transient errors and succeeds."""
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = True

    # Fail on first call, succeed on second call
    mock_client.delete_collection.side_effect = [
        RuntimeError("Transient network timeout"),
        True,
    ]

    provider = QdrantProvider(client=mock_client)
    res = await provider.delete_collection("retry_col")
    assert res is True
    assert mock_client.delete_collection.call_count == 2


# ---------------------------------------------------------------------------
# 4. VectorIndexManager Unit Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vector_index_manager_ensure_collection_missing() -> None:
    """Verify index manager creates missing collection."""
    mock_provider = MockVectorStoreProvider()
    manager = VectorIndexManager(provider=mock_provider, default_vector_size=768)

    created = await manager.ensure_collection_exists(
        collection_name="investiga_test",
        vector_size=768,
        distance=DistanceMetric.COSINE,
    )
    assert created is True
    assert await mock_provider.collection_exists("investiga_test") is True


@pytest.mark.asyncio
async def test_vector_index_manager_ensure_collection_existing() -> None:
    """Existing collection with matching schema returns False without recreating."""
    mock_provider = MockVectorStoreProvider()
    await mock_provider.create_collection("investiga_existing", vector_size=768)

    manager = VectorIndexManager(provider=mock_provider, default_vector_size=768)
    created = await manager.ensure_collection_exists(
        "investiga_existing", vector_size=768
    )
    assert created is False


@pytest.mark.asyncio
async def test_vector_index_manager_schema_mismatch() -> None:
    """Verify VectorDimensionMismatchException on dimension divergence."""
    mock_provider = MockVectorStoreProvider()
    await mock_provider.create_collection("mismatched_col", vector_size=384)

    manager = VectorIndexManager(provider=mock_provider, default_vector_size=768)
    with pytest.raises(VectorDimensionMismatchException) as exc_info:
        await manager.validate_schema("mismatched_col", expected_vector_size=768)

    assert exc_info.value.details["expected_dimension"] == 768
    assert exc_info.value.details["actual_dimension"] == 384


@pytest.mark.asyncio
async def test_vector_index_manager_dynamic_dimension_update() -> None:
    """Verify dynamic vector dimension update on the index manager."""
    mock_provider = MockVectorStoreProvider()
    manager = VectorIndexManager(provider=mock_provider, default_vector_size=768)

    manager.set_default_vector_size(1024)
    assert manager.default_vector_size == 1024

    with pytest.raises(ValueError):
        manager.set_default_vector_size(-1)


@pytest.mark.asyncio
async def test_vector_index_manager_reindex(
    sample_vector_records: list[VectorRecord],
) -> None:
    """Verify reindex migrates vectors between collections."""
    mock_provider = MockVectorStoreProvider()
    await mock_provider.create_collection("source_col", vector_size=768)
    await mock_provider.upsert("source_col", sample_vector_records)

    manager = VectorIndexManager(provider=mock_provider, default_vector_size=768)
    upserted = await manager.reindex_collection(
        source_collection="source_col",
        target_collection="target_col",
    )
    assert upserted == len(sample_vector_records)
    assert await mock_provider.collection_exists("target_col") is True


# ---------------------------------------------------------------------------
# 5. VectorRepository Unit Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vector_repository_crud(
    sample_vector_records: list[VectorRecord],
) -> None:
    """Verify generic VectorRepository persistence, search, retrieve, and delete flows."""
    mock_provider = MockVectorStoreProvider()
    await mock_provider.create_collection("investiga_repo_col", vector_size=768)

    settings = VectorStoreSettings(collection_name="investiga_repo_col")
    repo = VectorRepository(provider=mock_provider, settings=settings)

    # 1. Upsert
    saved = await repo.upsert_vectors(sample_vector_records)
    assert saved == len(sample_vector_records)

    # 2. Search
    search_res = await repo.search(query_vector=[0.1] * 768, limit=3)
    assert search_res.total_found == 3
    assert len(search_res.results) == 3

    # 3. Retrieve by IDs
    pids = [r.id for r in sample_vector_records[:2]]
    retrieved = await repo.retrieve_by_ids(pids)
    assert len(retrieved) == 2

    # 4. Delete by document ID
    assert isinstance(sample_vector_records[0].payload, VectorPayload)
    doc_id = sample_vector_records[0].payload.document_id
    del_count = await repo.delete_by_document(doc_id)
    assert del_count == len(sample_vector_records)

    # 5. Health check
    health = await repo.health_check()
    assert health["status"] == "healthy"


# ---------------------------------------------------------------------------
# 6. Configuration & Settings Unit Tests
# ---------------------------------------------------------------------------


def test_vectorstore_settings_defaults() -> None:
    """Verify VectorStoreSettings default values."""
    cfg = VectorStoreSettings()
    assert cfg.provider == "qdrant"
    assert cfg.host == "localhost"
    assert cfg.port == 6333
    assert cfg.grpc_port == 6334
    assert cfg.prefer_grpc is True
    assert cfg.distance_metric == "cosine"
    assert cfg.vector_size == 768
    assert cfg.batch_size == 100
    assert cfg.timeout == 10.0
    assert cfg.max_retries == 3


def test_root_settings_contains_vectorstore() -> None:
    """Verify root Settings contains vectorstore configuration domain."""
    settings = get_settings()
    assert hasattr(settings, "vectorstore")
    assert isinstance(settings.vectorstore, VectorStoreSettings)
    assert settings.vectorstore.collection_name == "investiga_knowledge"


# ---------------------------------------------------------------------------
# 7. Exception Hierarchy Tests
# ---------------------------------------------------------------------------


def test_exception_hierarchy() -> None:
    """Verify exception inheritance, status codes, and error codes."""
    exc1 = VectorStoreConnectionException(host="localhost", port=6333)
    assert exc1.status_code == 503
    assert exc1.error_code == "VECTOR_STORE_CONNECTION_FAILED"
    assert exc1.details["host"] == "localhost"

    exc2 = CollectionNotFoundException(collection_name="col_x")
    assert exc2.status_code == 404
    assert exc2.error_code == "VECTOR_COLLECTION_NOT_FOUND"

    exc3 = CollectionAlreadyExistsException(collection_name="col_y")
    assert exc3.status_code == 409
    assert exc3.error_code == "VECTOR_COLLECTION_ALREADY_EXISTS"

    exc4 = VectorDimensionMismatchException(expected_dim=768, actual_dim=384)
    assert exc4.status_code == 422
    assert exc4.error_code == "VECTOR_DIMENSION_MISMATCH"

    exc5 = VectorUpsertException(
        collection_name="col_z", record_count=10, reason="disk full"
    )
    assert exc5.status_code == 500
    assert exc5.error_code == "VECTOR_UPSERT_FAILED"
