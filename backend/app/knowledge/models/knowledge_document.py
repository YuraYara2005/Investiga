"""Knowledge Document Relational Domain Entity for Investiga.

This module defines the primary KnowledgeDocument model representing indexed
runbooks, incident post-mortems, configuration specs, and technical manuals.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.knowledge.models.enums import (
    DocumentCategory,
    EmbeddingStatus,
    ProcessingStatus,
)

if TYPE_CHECKING:
    from app.auth.models.user import User
    from app.knowledge.models.knowledge_chunk import KnowledgeChunk


class KnowledgeDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Relational entity representing an ingested knowledge management asset.

    Attributes:
        id: Globally unique UUID primary key.
        title: Human-readable display title of the document.
        description: Optional abstract or operational synopsis.
        original_filename: Original file name during client upload.
        stored_filename: Secure, collision-resistant storage identifier on disk or object store.
        file_extension: Canonical normalized extension (e.g., '.pdf', '.docx', '.md').
        mime_type: Standard IANA MIME type identifier.
        file_size: Size of the raw file in bytes.
        language: ISO 639-1 two-letter language code (default 'en').
        category: Operational classification (Runbook, Manual, Policy, etc.).
        tags: List of arbitrary string taxonomy tags.
        version: Monotonically increasing revision integer.
        checksum: Cryptographic SHA-256 digest of the raw document bytes for duplicate prevention.
        storage_path: Physical or object store reference URI.
        processing_status: Status of the document parsing and validation pipeline.
        embedding_status: Status of vector database embedding synchronization.
        uploaded_by: Foreign key UUID of the User who uploaded the document.
        created_at: UTC timestamp when the record was persisted.
        updated_at: UTC timestamp of last metadata mutation.
        is_deleted: Soft delete audit flag.
        deleted_at: UTC timestamp when the record was marked deleted.
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "knowledge_documents"

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="Human-readable title of the document.",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional synopsis or operational summary.",
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Original uploaded file name.",
    )
    stored_filename: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        doc="Secure unique storage filename on disk/object storage.",
    )
    file_extension: Mapped[str] = mapped_column(
        String(32),
        index=True,
        nullable=False,
        doc="Normalized file extension.",
    )
    mime_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        doc="IANA standard MIME content type.",
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        doc="Raw file size in bytes.",
    )
    language: Mapped[str] = mapped_column(
        String(10),
        default="en",
        nullable=False,
        doc="ISO 639-1 language code.",
    )
    category: Mapped[DocumentCategory] = mapped_column(
        Enum(
            DocumentCategory,
            name="document_category_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=DocumentCategory.OTHER,
        nullable=False,
        index=True,
        doc="Business classification category.",
    )
    tags: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        doc="Arbitrary JSON list of taxonomy tags.",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        doc="Document version number.",
    )
    checksum: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        doc="SHA-256 cryptographic hex digest of file content.",
    )
    storage_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        doc="Storage URI or filesystem path.",
    )
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(
            ProcessingStatus,
            name="processing_status_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=ProcessingStatus.UPLOADED,
        nullable=False,
        index=True,
        doc="Pipeline processing status.",
    )
    embedding_status: Mapped[EmbeddingStatus] = mapped_column(
        Enum(
            EmbeddingStatus,
            name="embedding_status_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=EmbeddingStatus.NOT_STARTED,
        nullable=False,
        index=True,
        doc="Vector embedding indexing status.",
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="User ID of the uploader.",
    )

    # Relationships
    uploader: Mapped["User"] = relationship(
        "User",
        lazy="selectin",
    )
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        "KnowledgeChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __init__(
        self,
        *,
        title: str,
        original_filename: str,
        stored_filename: str,
        file_extension: str,
        mime_type: str,
        file_size: int,
        checksum: str,
        storage_path: str,
        uploaded_by: uuid.UUID,
        description: str | None = None,
        language: str = "en",
        category: DocumentCategory = DocumentCategory.OTHER,
        tags: list[str] | None = None,
        version: int = 1,
        processing_status: ProcessingStatus = ProcessingStatus.UPLOADED,
        embedding_status: EmbeddingStatus = EmbeddingStatus.NOT_STARTED,
        is_deleted: bool = False,
        deleted_at: datetime | None = None,
        id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            title=title,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_extension=file_extension,
            mime_type=mime_type,
            file_size=file_size,
            checksum=checksum,
            storage_path=storage_path,
            uploaded_by=uploaded_by,
            description=description,
            language=language,
            category=category,
            tags=tags if tags is not None else [],
            version=version,
            processing_status=processing_status,
            embedding_status=embedding_status,
            is_deleted=is_deleted,
            deleted_at=deleted_at,
            id=id,
            **kwargs,
        )

    def __repr__(self) -> str:
        return (
            f"<KnowledgeDocument id={self.id} title='{self.title}' "
            f"category={self.category.value} status={self.processing_status.value}>"
        )
