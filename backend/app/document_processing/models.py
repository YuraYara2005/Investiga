"""Data Transfer Objects and Domain Models for Document Processing Pipeline.

Provides strongly-typed Pydantic v2 schemas representing extracted text,
file metadata, normalization configurations, and final processing results.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExtractedMetadata(BaseModel):
    """Metadata extracted directly from file headers, properties, or frontmatter."""

    model_config = ConfigDict(frozen=True)

    title: str | None = Field(
        default=None,
        description="Document title extracted from file metadata or frontmatter.",
    )
    author: str | None = Field(
        default=None,
        description="Author or creator name identified in document properties.",
    )
    creation_date: datetime | None = Field(
        default=None,
        description="Original document creation timestamp if present.",
    )
    modification_date: datetime | None = Field(
        default=None,
        description="Last modification timestamp if present.",
    )
    page_count: int = Field(
        default=1,
        ge=1,
        description="Total number of discrete pages or sections in the document.",
    )
    language: str | None = Field(
        default=None,
        description="Document language detected or specified in metadata.",
    )
    extra_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional parser-specific raw key-value metadata attributes.",
    )


class ExtractedDocument(BaseModel):
    """Intermediate container uniting raw parsed text with structural metadata."""

    model_config = ConfigDict(frozen=True)

    raw_text: str = Field(
        ...,
        description="Unmodified text extracted directly by the parser.",
    )
    metadata: ExtractedMetadata = Field(
        default_factory=ExtractedMetadata,
        description="Extracted document metadata attributes.",
    )


class ProcessingResult(BaseModel):
    """Final output emitted by DocumentProcessor after extraction, sanitization, and normalization."""

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    document_id: uuid.UUID | None = Field(
        default=None,
        description="Optional associated database document UUID.",
    )
    raw_text: str = Field(
        ...,
        description="Original raw text prior to cleaning and normalization.",
    )
    clean_text: str = Field(
        ...,
        description="Sanitized, Unicode-normalized, whitespace-collapsed textual payload.",
    )
    page_count: int = Field(
        default=1,
        ge=1,
        description="Total page count of parsed document.",
    )
    word_count: int = Field(
        default=0,
        ge=0,
        description="Total word count in cleaned text.",
    )
    character_count: int = Field(
        default=0,
        ge=0,
        description="Total character count in cleaned text.",
    )
    language: str | None = Field(
        default=None,
        description="Document language code.",
    )
    title: str | None = Field(
        default=None,
        description="Resolved document title.",
    )
    author: str | None = Field(
        default=None,
        description="Resolved author name.",
    )
    creation_date: datetime | None = Field(
        default=None,
        description="Creation date from metadata.",
    )
    modification_date: datetime | None = Field(
        default=None,
        description="Modification date from metadata.",
    )
    processing_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Total execution latency for parsing and cleaning in milliseconds.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Aggregated metadata and diagnostic attributes.",
    )
