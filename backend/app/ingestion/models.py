"""Domain Models and DTOs for the Document Ingestion Pipeline.

Encapsulates pipeline lifecycle statuses, ingestion options, execution telemetry
metrics, and comprehensive ingestion summary reports.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IngestionStatus(StrEnum):
    """Execution status of the end-to-end ingestion pipeline."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IngestionOptions(BaseModel):
    """Configurable execution parameters for document ingestion."""

    model_config = ConfigDict(frozen=True)

    chunk_size: int | None = Field(
        default=None,
        ge=64,
        le=8192,
        description="Override chunk token size. Defaults to system ChunkingSettings.",
    )
    overlap: int | None = Field(
        default=None,
        ge=0,
        description="Override chunk token overlap. Defaults to system ChunkingSettings.",
    )
    chunk_strategy: str | None = Field(
        default=None,
        description="Override chunking strategy ('adaptive', 'recursive_character', 'sentence', etc.).",
    )
    batch_size: int | None = Field(
        default=None,
        ge=1,
        le=512,
        description="Override embedding inference batch size.",
    )
    force_reindex: bool = Field(
        default=False,
        description="If True, delete existing vectors and chunks and re-run ingestion from scratch.",
    )
    metadata_override: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional additional metadata attributes to inject into vector payloads.",
    )


class IngestionMetrics(BaseModel):
    """Detailed latency and timing breakdown across all ingestion stages."""

    model_config = ConfigDict(frozen=True)

    total_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Total end-to-end pipeline execution duration in milliseconds.",
    )
    parsing_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time spent parsing the source document format into raw text.",
    )
    cleaning_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time spent normalizing and sanitizing text.",
    )
    chunking_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time spent partitioning clean text into semantic chunks.",
    )
    embedding_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time spent generating dense vector embeddings via the Embedding Engine.",
    )
    vector_upload_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time spent batch upserting vector points into Qdrant.",
    )
    database_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time spent persisting relational KnowledgeChunk rows and updating document status.",
    )


class IngestionReport(BaseModel):
    """Complete summary report returned upon pipeline execution completion."""

    model_config = ConfigDict(frozen=True)

    document_id: uuid.UUID = Field(
        description="UUID of the ingested KnowledgeDocument.",
    )
    status: IngestionStatus = Field(
        description="Final pipeline outcome status (COMPLETED or FAILED).",
    )
    original_filename: str = Field(
        description="Original name of the uploaded document file.",
    )
    file_size_bytes: int = Field(
        ge=0,
        description="Raw document file size in bytes.",
    )
    character_count: int = Field(
        ge=0,
        description="Total character count of the normalized text content.",
    )
    word_count: int = Field(
        ge=0,
        description="Total word count of the normalized text content.",
    )
    token_count: int = Field(
        ge=0,
        description="Total token count across all generated chunks.",
    )
    total_chunks: int = Field(
        ge=0,
        description="Number of intelligent chunks generated.",
    )
    total_vectors_stored: int = Field(
        ge=0,
        description="Number of vector points successfully indexed into Qdrant.",
    )
    embedding_model: str = Field(
        description="Name/identifier of the embedding model used.",
    )
    vector_dimension: int = Field(
        ge=1,
        description="Dimensionality of the generated vector embeddings.",
    )
    collection_name: str = Field(
        description="Qdrant vector collection name where vectors are stored.",
    )
    metrics: IngestionMetrics = Field(
        description="Stage-by-stage latency and duration metrics.",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="List of error messages or warnings encountered during execution.",
    )
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when the report was compiled.",
    )
