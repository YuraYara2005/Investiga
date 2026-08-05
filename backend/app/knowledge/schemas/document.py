"""Pydantic Data Transfer Objects (DTOs) for Knowledge Documents.

This module defines request and response schemas for ingesting, querying,
updating, and listing platform knowledge documents.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.knowledge.models.enums import (
    DocumentCategory,
    EmbeddingStatus,
    ProcessingStatus,
)


class UploadDocumentRequest(BaseModel):
    """Schema for registering a newly uploaded knowledge document metadata."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable title of the document.",
        examples=["Kubernetes Incident Response Runbook"],
    )
    description: str | None = Field(
        default=None,
        max_length=4096,
        description="Optional synopsis or operational summary.",
        examples=["Standard procedure for resolving NodeNotReady alerts."],
    )
    original_filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Original uploaded filename.",
        examples=["k8s_runbook_v2.pdf"],
    )
    stored_filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Secure collision-resistant storage identifier.",
        examples=["doc_9b1deb4d3b7d4e89_k8s_runbook_v2.pdf"],
    )
    file_extension: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Normalized file extension.",
        examples=[".pdf"],
    )
    mime_type: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Standard IANA MIME content type.",
        examples=["application/pdf"],
    )
    file_size: int = Field(
        ...,
        gt=0,
        description="Raw document size in bytes.",
        examples=[2048576],
    )
    language: str = Field(
        default="en",
        min_length=2,
        max_length=10,
        description="ISO 639-1 two-letter language code.",
        examples=["en"],
    )
    category: DocumentCategory = Field(
        default=DocumentCategory.OTHER,
        description="Business classification domain.",
        examples=[DocumentCategory.RUNBOOK],
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Categorization and taxonomy tags.",
        examples=[["kubernetes", "incident-response", "sre"]],
    )
    version: int = Field(
        default=1,
        ge=1,
        description="Document version integer.",
        examples=[1],
    )
    checksum: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="SHA-256 cryptographic hex digest of document content.",
        examples=["e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"],
    )
    storage_path: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Storage path URI or filesystem destination.",
        examples=["s3://investiga-knowledge/runbooks/2026/k8s.pdf"],
    )


class UpdateDocumentRequest(BaseModel):
    """Schema for modifying knowledge document metadata and state."""

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated document title.",
    )
    description: str | None = Field(
        default=None,
        max_length=4096,
        description="Updated description or abstract.",
    )
    language: str | None = Field(
        default=None,
        min_length=2,
        max_length=10,
        description="Updated language code.",
    )
    category: DocumentCategory | None = Field(
        default=None,
        description="Updated classification category.",
    )
    tags: list[str] | None = Field(
        default=None,
        description="Updated taxonomy tag list.",
    )
    processing_status: ProcessingStatus | None = Field(
        default=None,
        description="Updated pipeline processing status.",
    )
    embedding_status: EmbeddingStatus | None = Field(
        default=None,
        description="Updated vector database indexing status.",
    )


class KnowledgeDocumentResponse(BaseModel):
    """Public representation of a KnowledgeDocument entity."""

    id: uuid.UUID
    title: str
    description: str | None
    original_filename: str
    stored_filename: str
    file_extension: str
    mime_type: str
    file_size: int
    language: str
    category: DocumentCategory
    tags: list[str]
    version: int
    checksum: str
    storage_path: str
    processing_status: ProcessingStatus
    embedding_status: EmbeddingStatus
    uploaded_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    deleted_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class KnowledgeDocumentListResponse(BaseModel):
    """Paginated collection response for knowledge documents."""

    items: list[KnowledgeDocumentResponse]
    total: int
    skip: int
    limit: int
