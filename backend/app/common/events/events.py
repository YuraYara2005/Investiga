"""Domain Event Definitions for Investiga.

Provides domain event abstractions emitted across the ingestion and knowledge
lifecycle stages to enable lightweight, in-process decoupled handlers with zero
external message broker dependencies, while remaining effortlessly swappable for
distributed brokers (e.g. Kafka, RabbitMQ, Redis) in the future.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    """Base domain event model capturing event identity and timestamp."""

    event_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        description="Globally unique identifier for this event instance.",
    )
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when the domain event occurred.",
    )
    event_type: str = Field(
        default="DomainEvent",
        description="Discriminator name identifying the event schema.",
    )


class DocumentUploaded(DomainEvent):
    """Emitted when an operational document is uploaded and registered in storage."""

    event_type: str = "DocumentUploaded"
    document_id: uuid.UUID
    user_id: uuid.UUID
    original_filename: str
    stored_filename: str
    file_size_bytes: int
    checksum: str
    mime_type: str


class DocumentParsed(DomainEvent):
    """Emitted when raw text and structural metadata are extracted and cleaned."""

    event_type: str = "DocumentParsed"
    document_id: uuid.UUID
    character_count: int
    word_count: int
    page_count: int
    duration_ms: float


class DocumentChunked(DomainEvent):
    """Emitted when document text is partitioned into intelligent semantic chunks."""

    event_type: str = "DocumentChunked"
    document_id: uuid.UUID
    chunk_count: int
    total_tokens: int
    strategy: str
    duration_ms: float


class EmbeddingsGenerated(DomainEvent):
    """Emitted when dense vector representations are computed for all chunks."""

    event_type: str = "EmbeddingsGenerated"
    document_id: uuid.UUID
    embedding_count: int
    dimension: int
    model_name: str
    duration_ms: float


class VectorsIndexed(DomainEvent):
    """Emitted when vector points and metadata payloads are persisted in Qdrant."""

    event_type: str = "VectorsIndexed"
    document_id: uuid.UUID
    vector_count: int
    collection_name: str
    duration_ms: float


class IngestionCompleted(DomainEvent):
    """Emitted when the complete end-to-end ingestion pipeline finishes successfully."""

    event_type: str = "IngestionCompleted"
    document_id: uuid.UUID
    total_chunks: int
    total_vectors: int
    total_tokens: int
    total_duration_ms: float
    report_summary: dict[str, Any] = Field(default_factory=dict)


class IngestionFailed(DomainEvent):
    """Emitted when any stage of the ingestion pipeline fails."""

    event_type: str = "IngestionFailed"
    document_id: uuid.UUID
    stage: str
    error_type: str
    error_message: str
    total_duration_ms: float


# Type aliases for alternative naming conventions
DocumentUploadedEvent = DocumentUploaded
DocumentParsedEvent = DocumentParsed
DocumentChunkedEvent = DocumentChunked
EmbeddingsGeneratedEvent = EmbeddingsGenerated
VectorsIndexedEvent = VectorsIndexed
IngestionCompletedEvent = IngestionCompleted
IngestionFailedEvent = IngestionFailed
