"""Vector Store Domain Models.

Pydantic v2 schemas representing vector payloads with multi-tenancy, rich metadata,
vector records, scored search results, collection diagnostics, and distance metrics.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DistanceMetric(StrEnum):
    """Supported vector distance similarity metrics."""

    COSINE = "cosine"
    DOT = "dot"
    EUCLIDEAN = "euclidean"
    MANHATTAN = "manhattan"


class VectorPayload(BaseModel):
    """Structured, enterprise-grade vector payload attached to each indexed vector point.

    Includes strict multi-tenancy isolation attributes, rich provenance metadata,
    re-indexing version tags, and text fields prepared for future hybrid search.
    """

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    # Multi-tenancy & Isolation
    tenant_id: uuid.UUID | str | None = Field(
        default=None,
        description="Tenant identifier for multi-tenant isolation.",
    )
    workspace_id: uuid.UUID | str | None = Field(
        default=None,
        description="Workspace identifier within a tenant.",
    )
    organization_id: uuid.UUID | str | None = Field(
        default=None,
        description="Organization identifier for access boundaries.",
    )
    visibility: str = Field(
        default="private",
        description="Visibility scope ('private', 'workspace', 'organization', 'public').",
    )

    # Document & Chunk Identity
    document_id: uuid.UUID | str = Field(
        description="Identifier of the parent source document.",
    )
    chunk_id: uuid.UUID | str = Field(
        description="Identifier of the specific text chunk.",
    )
    chunk_index: int = Field(
        default=0,
        ge=0,
        description="Sequential index of the chunk within the document.",
    )
    document_version: int = Field(
        default=1,
        ge=1,
        description="Version number of the source document.",
    )

    # Provenance & File Attributes
    source: str = Field(
        default="document_upload",
        description="Origin channel or ingestion pathway.",
    )
    source_type: str = Field(
        default="file",
        description="Type of source ('file', 'web', 'api', 'manual').",
    )
    file_name: str = Field(
        default="",
        description="Original name of the source file.",
    )
    title: str | None = Field(
        default=None,
        description="Document or section title.",
    )
    category: str | None = Field(
        default=None,
        description="Semantic category or classification tag.",
    )
    mime_type: str = Field(
        default="application/octet-stream",
        description="MIME type of the source artifact.",
    )
    checksum: str = Field(
        default="",
        description="SHA-256 or MD5 hash of the source document content.",
    )
    page_number: int | None = Field(
        default=None,
        ge=1,
        description="Page number where the chunk content originated.",
    )
    heading: str | None = Field(
        default=None,
        description="Section heading or markdown title under which the chunk appears.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Categorical tags attached to the document or chunk.",
    )

    # Authorship & Lifecycle Timestamps
    created_by: uuid.UUID | str | None = Field(
        default=None,
        description="User or service identity that ingested the document.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when the source entity was created.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when the source entity was last modified.",
    )
    indexed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when this vector was indexed into the vector store.",
    )

    # Content & Processing Metrics
    language: str = Field(
        default="en",
        description="ISO 639-1 language code.",
    )
    word_count: int = Field(
        default=0,
        ge=0,
        description="Number of words in the chunk text.",
    )
    character_count: int = Field(
        default=0,
        ge=0,
        description="Number of characters in the chunk text.",
    )
    token_count: int = Field(
        default=0,
        ge=0,
        description="Number of tokens according to the tokenizer.",
    )
    processing_version: str = Field(
        default="1.0.0",
        description="Version of the document processing pipeline used.",
    )
    parser_version: str = Field(
        default="1.0.0",
        description="Version of the parser used.",
    )
    chunk_strategy: str = Field(
        default="adaptive",
        description="Chunking strategy used ('fixed_character', 'sentence', 'paragraph', 'markdown_header', 'adaptive').",
    )

    # Embedding Provenance
    embedding_model: str = Field(
        default="BAAI/bge-base-en-v1.5",
        description="Model identifier that produced the vector embedding.",
    )
    embedding_provider: str = Field(
        default="SentenceTransformerProvider",
        description="Provider class name that executed inference.",
    )
    embedding_dimension: int = Field(
        default=768,
        ge=1,
        description="Embedding vector dimensionality.",
    )

    # Hybrid Search Preparation
    raw_text: str | None = Field(
        default=None,
        description="Original raw chunk text before embedding (enables hybrid sparse/dense retrieval).",
    )
    normalized_text: str | None = Field(
        default=None,
        description="Cleaned, normalized text content.",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Extracted keywords for sparse/lexical indexing.",
    )

    # Arbitrary Extended Metadata
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional custom attributes for flexible enterprise extension.",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to a JSON-serializable dictionary for vector database storage."""
        data = self.model_dump(mode="json")
        # Ensure UUIDs are serialized as strings
        for key, val in data.items():
            if isinstance(val, uuid.UUID):
                data[key] = str(val)
        return data


class VectorRecord(BaseModel):
    """Represents a single vector point to be stored or retrieved."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str | uuid.UUID = Field(
        description="Unique identifier for the vector record (point ID).",
    )
    vector: list[float] = Field(
        description="Dense float embedding vector.",
    )
    payload: VectorPayload | dict[str, Any] = Field(
        default_factory=dict,
        description="Structured metadata payload associated with this vector.",
    )

    @property
    def id_str(self) -> str:
        """Return the ID as a string."""
        return str(self.id)

    @property
    def payload_dict(self) -> dict[str, Any]:
        """Return payload as a dictionary."""
        if isinstance(self.payload, VectorPayload):
            return self.payload.to_dict()
        return dict(self.payload)


class ScoredVectorRecord(BaseModel):
    """Represents a similarity search result with score and associated payload."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str | uuid.UUID = Field(
        description="Unique identifier of the matching vector point.",
    )
    score: float = Field(
        description="Similarity or relevance score computed by the vector database.",
    )
    vector: list[float] | None = Field(
        default=None,
        description="Dense embedding vector if requested.",
    )
    payload: VectorPayload | dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata payload stored with the vector point.",
    )

    @property
    def id_str(self) -> str:
        """Return point ID as a string."""
        return str(self.id)

    @property
    def payload_dict(self) -> dict[str, Any]:
        """Return payload guaranteed as a dictionary."""
        if isinstance(self.payload, VectorPayload):
            return self.payload.to_dict()
        return self.payload


class CollectionStats(BaseModel):
    """Diagnostic metrics and metadata describing a vector store collection."""

    model_config = ConfigDict(frozen=True)

    collection_name: str = Field(
        description="Name of the collection / index.",
    )
    status: str = Field(
        description="Collection status ('green', 'yellow', 'red', 'active', etc.).",
    )
    vectors_count: int = Field(
        ge=0,
        description="Total number of vectors in the collection.",
    )
    indexed_vectors_count: int = Field(
        ge=0,
        description="Number of indexed vectors available for search.",
    )
    points_count: int = Field(
        ge=0,
        description="Total point count in the collection.",
    )
    segments_count: int = Field(
        ge=0,
        description="Number of segments in the storage engine.",
    )
    vector_size: int = Field(
        ge=1,
        description="Dimensionality of vectors in this collection.",
    )
    distance: str = Field(
        description="Distance metric configured for this collection.",
    )


class VectorSearchResult(BaseModel):
    """Container for vector similarity search results with execution telemetry."""

    model_config = ConfigDict(frozen=True)

    collection_name: str = Field(
        description="Name of the collection queried.",
    )
    query_vector_dim: int = Field(
        ge=1,
        description="Dimensionality of the query vector.",
    )
    results: list[ScoredVectorRecord] = Field(
        default_factory=list,
        description="Ranked list of matching vector records.",
    )
    total_found: int = Field(
        ge=0,
        description="Number of results matching the query criteria.",
    )
    latency_ms: float = Field(
        ge=0.0,
        description="Wall-clock query execution latency in milliseconds.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Diagnostic telemetry and filter attributes applied.",
    )
