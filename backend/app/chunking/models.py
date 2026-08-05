"""Chunk Domain Models.

Pydantic v2 schemas representing individual text chunks, associated metadata,
and final chunking results used downstream by the embedding pipeline.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChunkMetadata(BaseModel):
    """Preserved contextual attributes from the source document attached to each chunk."""

    model_config = ConfigDict(frozen=True)

    document_id: uuid.UUID | None = Field(
        default=None,
        description="UUID of the parent KnowledgeDocument entity.",
    )
    source_filename: str | None = Field(
        default=None,
        description="Original filename of the source document.",
    )
    language: str = Field(
        default="en",
        description="ISO 639-1 language code for the chunk text.",
    )
    section_title: str | None = Field(
        default=None,
        description="Section or heading title the chunk belongs to.",
    )
    page_number: int | None = Field(
        default=None,
        ge=1,
        description="Page number in source document where this chunk originates.",
    )
    chunk_index: int = Field(
        default=0,
        ge=0,
        description="Zero-based sequential index of this chunk within the document.",
    )
    total_chunks: int = Field(
        default=1,
        ge=1,
        description="Total number of chunks produced from the parent document.",
    )
    strategy: str = Field(
        default="fixed_character",
        description="Chunking strategy that produced this chunk.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when this chunk was generated.",
    )
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional strategy-specific diagnostic attributes.",
    )


class Chunk(BaseModel):
    """Atomic text segment produced by the chunking pipeline."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    chunk_id: uuid.UUID = Field(
        description="Deterministic UUID v5 derived from document_id + chunk_index + text hash.",
    )
    document_id: uuid.UUID | None = Field(
        default=None,
        description="Parent document identifier.",
    )
    chunk_index: int = Field(
        ge=0,
        description="Zero-based sequential position of this chunk within the document.",
    )
    text: str = Field(
        description="Extracted text content of this chunk.",
    )
    start_offset: int = Field(
        ge=0,
        description="Character offset in the original clean_text where this chunk begins.",
    )
    end_offset: int = Field(
        ge=0,
        description="Character offset in the original clean_text where this chunk ends (exclusive).",
    )
    token_count: int = Field(
        ge=0,
        description="Estimated or exact token count for this chunk's text.",
    )
    character_count: int = Field(
        ge=0,
        description="Total character count of the chunk text.",
    )
    section_title: str | None = Field(
        default=None,
        description="Nearest heading or section title that contextualizes this chunk.",
    )
    page_number: int | None = Field(
        default=None,
        ge=1,
        description="Estimated source page number.",
    )
    checksum: str = Field(
        description="SHA-256 hex digest of the chunk text for integrity verification.",
    )
    metadata: ChunkMetadata = Field(
        description="Rich contextual metadata from source document.",
    )

    @staticmethod
    def compute_checksum(text: str) -> str:
        """Compute SHA-256 hex checksum of the chunk text."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def compute_chunk_id(
        document_id: uuid.UUID | None,
        chunk_index: int,
        text: str,
    ) -> uuid.UUID:
        """Generate deterministic UUID v5 for the chunk.

        UUID is derived from a composite namespace of document_id, chunk_index, and a SHA-256
        digest of the text to ensure identical re-generation from identical inputs.

        Args:
            document_id: Parent document UUID or None for unbound chunks.
            chunk_index: Zero-based chunk position.
            text: Chunk text content.

        Returns:
            uuid.UUID: Deterministic v5 UUID.
        """
        text_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        doc_str = str(document_id) if document_id is not None else "no-document"
        namespace_seed = f"{doc_str}:{chunk_index}:{text_digest}"
        return uuid.uuid5(uuid.NAMESPACE_DNS, namespace_seed)


class ChunkResult(BaseModel):
    """Aggregate container returned by the ChunkingEngine after processing a document."""

    model_config = ConfigDict(frozen=True)

    document_id: uuid.UUID | None = Field(
        default=None,
        description="Parent document identifier.",
    )
    chunks: list[Chunk] = Field(
        default_factory=list,
        description="Ordered list of generated text chunks.",
    )
    total_chunks: int = Field(
        ge=0,
        description="Total number of chunks produced.",
    )
    strategy_used: str = Field(
        description="Name of the chunking strategy that produced these chunks.",
    )
    chunk_size: int = Field(
        ge=1,
        description="Configured maximum token size per chunk.",
    )
    overlap: int = Field(
        ge=0,
        description="Configured overlap token count between adjacent chunks.",
    )
    total_tokens: int = Field(
        ge=0,
        description="Sum of token counts across all produced chunks.",
    )
    processing_time_ms: float = Field(
        ge=0.0,
        description="Wall-clock time in milliseconds to generate all chunks.",
    )
