"""Retrieval Domain Models, DTOs, and Telemetry Structures.

Defines search requests, options, structured filters, candidate representations,
fused retrieved chunks, telemetry metrics, and observability traces for the
Enterprise Hybrid Retrieval Engine.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.vectorstore.filters import MetadataFilterBuilder


class SearchFilters(BaseModel):
    """Structured, multi-dimensional search filter specification."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    document_ids: list[uuid.UUID | str] | None = Field(
        default=None,
        description="Filter to specific parent document identifiers.",
    )
    category: str | None = Field(
        default=None,
        description="Filter to a specific business document category.",
    )
    source: str | None = Field(
        default=None,
        description="Filter by provenance source.",
    )
    language: str | None = Field(
        default=None,
        description="Filter by ISO 639-1 language code.",
    )
    tags: list[str] | None = Field(
        default=None,
        description="Require matching categorical tags.",
    )
    created_by: uuid.UUID | str | None = Field(
        default=None,
        description="Filter by user or service creator UUID.",
    )
    tenant_id: uuid.UUID | str | None = Field(
        default=None,
        description="Multi-tenant isolation boundary identifier.",
    )
    workspace_id: uuid.UUID | str | None = Field(
        default=None,
        description="Workspace boundary identifier.",
    )
    created_after: datetime | None = Field(
        default=None,
        description="Filter for documents created at or after this UTC timestamp.",
    )
    created_before: datetime | None = Field(
        default=None,
        description="Filter for documents created at or before this UTC timestamp.",
    )
    custom_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary additional key-value filter conditions.",
    )

    def is_empty(self) -> bool:
        """Return True if no active filter criteria are defined."""
        return (
            self.document_ids is None
            and self.category is None
            and self.source is None
            and self.language is None
            and not self.tags
            and self.created_by is None
            and self.tenant_id is None
            and self.workspace_id is None
            and self.created_after is None
            and self.created_before is None
            and not self.custom_metadata
        )

    def to_filter_builder(self) -> MetadataFilterBuilder:
        """Convert structured filters into a vector store MetadataFilterBuilder."""
        builder = MetadataFilterBuilder()
        if self.tenant_id:
            builder.filter_tenant(self.tenant_id)
        if self.workspace_id:
            builder.filter_workspace(self.workspace_id)
        if self.document_ids:
            if len(self.document_ids) == 1:
                builder.filter_document(self.document_ids[0])
            else:
                builder.filter_in("document_id", list(self.document_ids))
        if self.category:
            builder.must("category", self.category)
        if self.source:
            builder.must("source", self.source)
        if self.language:
            builder.must("language", self.language)
        if self.created_by:
            builder.must("created_by", str(self.created_by))
        if self.tags:
            for tag in self.tags:
                builder.must("tags", tag)
        if self.created_after or self.created_before:
            gte_val = self.created_after.timestamp() if self.created_after else None
            lte_val = self.created_before.timestamp() if self.created_before else None
            builder.filter_range("created_at", gte=gte_val, lte=lte_val)

        for k, v in self.custom_metadata.items():
            if isinstance(v, list):
                builder.filter_in(k, v)
            else:
                builder.must(k, v)

        return builder

    def matches_dict(self, payload: dict[str, Any]) -> bool:
        """Evaluate whether a candidate metadata payload satisfies these filter rules."""
        if self.tenant_id:
            if str(payload.get("tenant_id", "")) != str(self.tenant_id):
                return False
        if self.workspace_id:
            if str(payload.get("workspace_id", "")) != str(self.workspace_id):
                return False
        if self.document_ids:
            doc_id_str = str(payload.get("document_id", ""))
            allowed = {str(d) for d in self.document_ids}
            if doc_id_str not in allowed:
                return False
        if self.category:
            if payload.get("category") != self.category:
                return False
        if self.source:
            if payload.get("source") != self.source:
                return False
        if self.language:
            if payload.get("language") != self.language:
                return False
        if self.created_by:
            if str(payload.get("created_by", "")) != str(self.created_by):
                return False
        if self.tags:
            payload_tags = payload.get("tags") or []
            if isinstance(payload_tags, str):
                payload_tags = [payload_tags]
            for tag in self.tags:
                if tag not in payload_tags:
                    return False
        for k, v in self.custom_metadata.items():
            if payload.get(k) != v:
                return False
        return True


class SearchOptions(BaseModel):
    """Configurable execution parameters for hybrid retrieval."""

    model_config = ConfigDict(frozen=True)

    top_k: int = Field(
        default=20,
        ge=1,
        le=1000,
        description="Number of final ranked chunks to return.",
    )
    dense_candidate_limit: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Candidate limit retrieved from dense vector search.",
    )
    sparse_candidate_limit: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Candidate limit retrieved from BM25 sparse keyword search.",
    )
    dense_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight coefficient assigned to dense retrieval.",
    )
    sparse_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight coefficient assigned to sparse BM25 retrieval.",
    )
    rrf_k: int = Field(
        default=60,
        ge=1,
        le=1000,
        description="Reciprocal Rank Fusion smoothing constant k.",
    )
    min_score_threshold: float = Field(
        default=0.0,
        ge=0.0,
        description="Minimum score threshold for a chunk to be returned.",
    )
    enabled_dense: bool = Field(
        default=True,
        description="Whether dense vector search is executed.",
    )
    enabled_sparse: bool = Field(
        default=True,
        description="Whether sparse BM25 keyword search is executed.",
    )
    fusion_strategy: str = Field(
        default="rrf",
        description="Fusion strategy identifier ('rrf', 'weighted_linear', 'combsum').",
    )
    enable_cache: bool = Field(
        default=True,
        description="Whether to check and update retrieval cache.",
    )
    collection_name: str | None = Field(
        default=None,
        description="Override target vector collection name.",
    )
    timeout_seconds: float = Field(
        default=10.0,
        ge=0.001,
        description="Execution timeout in seconds.",
    )


class SearchQuery(BaseModel):
    """Encapsulates a search query with optional filters and execution options."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    query: str = Field(
        description="Raw user query string.",
    )
    filters: SearchFilters | None = Field(
        default=None,
        description="Optional structured metadata filters.",
    )
    options: SearchOptions | None = Field(
        default=None,
        description="Optional runtime execution parameters.",
    )


class CandidateChunk(BaseModel):
    """Intermediate candidate chunk produced by a single retrieval strategy."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    chunk_id: uuid.UUID | str = Field(
        description="Unique chunk identifier matching vector and database IDs.",
    )
    document_id: uuid.UUID | str = Field(
        description="Parent document UUID.",
    )
    chunk_index: int = Field(
        default=0,
        ge=0,
        description="Sequential index of the chunk.",
    )
    text: str = Field(
        description="Text content of the chunk.",
    )
    score: float = Field(
        description="Relevance or similarity score assigned by the strategy.",
    )
    rank: int = Field(
        ge=1,
        description="1-based ordinal rank within the strategy's candidate list.",
    )
    strategy_name: str = Field(
        description="Name of the strategy that retrieved this candidate ('dense', 'bm25', etc.).",
    )
    heading: str | None = Field(
        default=None,
        description="Section heading or title if available.",
    )
    page_number: int | None = Field(
        default=None,
        description="Document page number if available.",
    )
    title: str | None = Field(
        default=None,
        description="Source document title.",
    )
    file_name: str | None = Field(
        default=None,
        description="Original uploaded file name.",
    )
    category: str | None = Field(
        default=None,
        description="Document business classification category.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Document taxonomy tags.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Full unstructured metadata payload.",
    )

    @property
    def chunk_id_str(self) -> str:
        """String representation of chunk ID."""
        return str(self.chunk_id)

    @property
    def document_id_str(self) -> str:
        """String representation of document ID."""
        return str(self.document_id)


class RetrievedChunk(BaseModel):
    """Final ranked, deduplicated chunk produced by hybrid fusion."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    chunk_id: uuid.UUID | str = Field(
        description="Unique chunk identifier.",
    )
    document_id: uuid.UUID | str = Field(
        description="Parent document UUID.",
    )
    chunk_index: int = Field(
        default=0,
        ge=0,
        description="0-based sequential chunk index within the document.",
    )
    text: str = Field(
        description="Normalized text content of the chunk.",
    )
    score: float = Field(
        description="Final fused relevance score.",
    )
    dense_score: float | None = Field(
        default=None,
        description="Raw score from dense vector search (if matched).",
    )
    dense_rank: int | None = Field(
        default=None,
        description="1-based rank from dense vector search (if matched).",
    )
    sparse_score: float | None = Field(
        default=None,
        description="Raw score from sparse BM25 search (if matched).",
    )
    sparse_rank: int | None = Field(
        default=None,
        description="1-based rank from sparse BM25 search (if matched).",
    )
    retrieval_sources: list[str] = Field(
        default_factory=list,
        description="List of strategies that found this chunk (e.g. ['dense', 'bm25']).",
    )
    heading: str | None = Field(
        default=None,
        description="Section heading or markdown title.",
    )
    page_number: int | None = Field(
        default=None,
        description="Source document page number.",
    )
    title: str | None = Field(
        default=None,
        description="Document or section title.",
    )
    file_name: str | None = Field(
        default=None,
        description="Original source file name.",
    )
    category: str | None = Field(
        default=None,
        description="Document operational category.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Categorical tags attached to the chunk.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Attached metadata dictionary.",
    )

    @property
    def chunk_id_str(self) -> str:
        """String representation of chunk ID."""
        return str(self.chunk_id)

    @property
    def document_id_str(self) -> str:
        """String representation of document ID."""
        return str(self.document_id)


class RetrievalMetrics(BaseModel):
    """Granular latency and telemetry metrics for retrieval pipeline execution."""

    model_config = ConfigDict(frozen=True)

    query_prep_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time spent validating and normalizing query text.",
    )
    embedding_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time spent generating query embedding vector.",
    )
    dense_search_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time spent executing dense vector search in Qdrant.",
    )
    sparse_search_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time spent executing sparse BM25 keyword search.",
    )
    fusion_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time spent fusing, normalizing, deduplicating, and ranking results.",
    )
    total_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Total wall-clock duration of the retrieval operation.",
    )
    dense_candidates_count: int = Field(
        default=0,
        ge=0,
        description="Number of candidate records returned by dense search.",
    )
    sparse_candidates_count: int = Field(
        default=0,
        ge=0,
        description="Number of candidate records returned by BM25 search.",
    )
    fused_candidates_count: int = Field(
        default=0,
        ge=0,
        description="Number of distinct candidates processed during fusion.",
    )
    returned_chunks_count: int = Field(
        default=0,
        ge=0,
        description="Final number of ranked chunks returned to caller.",
    )
    top_score: float = Field(
        default=0.0,
        description="Highest score among returned chunks.",
    )
    average_score: float = Field(
        default=0.0,
        description="Average score across returned chunks.",
    )


class RetrievalTrace(BaseModel):
    """Observability trace capturing end-to-end retrieval context for debugging and analytics."""

    model_config = ConfigDict(frozen=True)

    query: str = Field(
        description="Original input query string.",
    )
    normalized_query: str = Field(
        description="Normalized query text used for execution.",
    )
    embedding_model: str = Field(
        default="unknown",
        description="Embedding model identifier used for dense retrieval.",
    )
    retrieval_strategies: list[str] = Field(
        default_factory=list,
        description="List of retrieval strategies executed.",
    )
    fusion_strategy: str = Field(
        default="rrf",
        description="Fusion algorithm applied.",
    )
    dense_candidates: int = Field(
        default=0,
        ge=0,
        description="Number of candidates retrieved from dense index.",
    )
    sparse_candidates: int = Field(
        default=0,
        ge=0,
        description="Number of candidates retrieved from sparse index.",
    )
    returned_chunks: int = Field(
        default=0,
        ge=0,
        description="Number of chunks returned after fusion and thresholding.",
    )
    latencies: dict[str, float] = Field(
        default_factory=dict,
        description="Dictionary mapping stage names to latency in milliseconds.",
    )
    cache_hit: bool = Field(
        default=False,
        description="Whether this retrieval was served from cache.",
    )
    partial_failure: bool = Field(
        default=False,
        description="Whether one of the retrieval strategies experienced a degraded failure.",
    )
    failure_reasons: list[str] = Field(
        default_factory=list,
        description="List of failure messages if partial failure occurred.",
    )
    retrieval_sources: list[str] = Field(
        default_factory=list,
        description="List of sources represented in the final result set.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of the retrieval execution.",
    )


class RetrievalResult(BaseModel):
    """Complete container encapsulating ranked chunks, telemetry, applied filters, and trace."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    query: str = Field(
        description="Original query text.",
    )
    normalized_query: str = Field(
        description="Normalized query text.",
    )
    chunks: list[RetrievedChunk] = Field(
        default_factory=list,
        description="Ranked list of retrieved knowledge chunks.",
    )
    total_found: int = Field(
        default=0,
        ge=0,
        description="Total matching candidates before top_k truncation.",
    )
    applied_filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Dictionary of filters applied during retrieval.",
    )
    metrics: RetrievalMetrics = Field(
        default_factory=RetrievalMetrics,
        description="Execution duration and candidate count metrics.",
    )
    trace: RetrievalTrace | None = Field(
        default=None,
        description="Observability trace for diagnostics and evaluation.",
    )
