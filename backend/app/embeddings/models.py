"""Embedding Domain Models.

Pydantic v2 schemas representing embedding vectors, batch results,
provider metadata, and normalization containers.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EmbeddingVector(BaseModel):
    """A single embedding vector with associated metadata."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    text_id: str = Field(
        description="Identifier for the source text (chunk_id, document_id, or ad-hoc key).",
    )
    text: str = Field(
        description="Original text that was embedded.",
    )
    vector: list[float] = Field(
        description="Dense embedding vector as list of floats.",
    )
    dimension: int = Field(
        ge=1,
        description="Dimensionality of the embedding vector.",
    )
    model_name: str = Field(
        description="Name of the embedding model that produced this vector.",
    )
    is_normalized: bool = Field(
        default=True,
        description="Whether the vector is L2-normalized.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when this embedding was generated.",
    )


class BatchEmbeddingResult(BaseModel):
    """Aggregate result from a batch embedding operation."""

    model_config = ConfigDict(frozen=True)

    batch_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        description="Unique ID for this batch execution.",
    )
    embeddings: list[EmbeddingVector] = Field(
        default_factory=list,
        description="Ordered list of embedding vectors.",
    )
    total_texts: int = Field(
        ge=0,
        description="Total number of texts submitted for embedding.",
    )
    successful_embeddings: int = Field(
        ge=0,
        description="Number of texts successfully embedded.",
    )
    model_name: str = Field(
        description="Embedding model used.",
    )
    dimension: int = Field(
        ge=1,
        description="Vector dimensionality produced.",
    )
    latency_ms: float = Field(
        ge=0.0,
        description="Total wall-clock latency for the full batch in milliseconds.",
    )
    throughput_texts_per_sec: float = Field(
        ge=0.0,
        description="Texts embedded per second.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional diagnostic metadata.",
    )


class EmbeddingModelInfo(BaseModel):
    """Metadata describing a loaded embedding model."""

    model_config = ConfigDict(frozen=True)

    model_name: str = Field(
        description="HuggingFace model identifier or local path.",
    )
    provider: str = Field(
        description="Provider implementation class name.",
    )
    dimension: int = Field(
        ge=1,
        description="Output embedding dimension.",
    )
    max_seq_length: int = Field(
        ge=1,
        description="Maximum input token sequence length.",
    )
    device: str = Field(
        description="Compute device: 'cuda', 'mps', or 'cpu'.",
    )
    normalize_embeddings: bool = Field(
        default=True,
        description="Whether this provider normalizes output vectors.",
    )
    loaded_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when the model was loaded into memory.",
    )
