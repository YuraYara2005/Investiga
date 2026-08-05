"""Knowledge Chunk Relational Domain Entity for Investiga.

This module defines the relational KnowledgeChunk model representing individual
semantic text chunks derived from KnowledgeDocument entities, indexed in PostgreSQL
for auditing, analytics, debugging, and hybrid/BM25 search synchronization.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.knowledge.models.knowledge_document import KnowledgeDocument


class KnowledgeChunk(Base, UUIDPrimaryKeyMixin):
    """Relational entity representing a chunk of an ingested KnowledgeDocument.

    Attributes:
        id: Globally unique UUID primary key (matches Qdrant vector point ID).
        document_id: UUID foreign key reference to the parent KnowledgeDocument.
        chunk_index: 0-indexed ordinal sequence number of the chunk within the document.
        text: Normalized textual content of the chunk.
        page_number: Optional 1-based page number where the chunk content originated.
        heading: Optional markdown heading or section title associated with the chunk.
        token_count: Number of tokens computed by the tokenizer for this chunk.
        character_count: Total raw character count of the chunk text.
        checksum: Cryptographic SHA-256 digest of the chunk text for auditing and deduplication.
        created_at: UTC timestamp when the chunk was persisted.
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "knowledge_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key UUID referencing parent KnowledgeDocument.",
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="0-based sequential index of the chunk within the source document.",
    )
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Normalized text content of the chunk.",
    )
    page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Source document page number (1-based), if available.",
    )
    heading: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        doc="Section heading or title hierarchy under which the chunk resides.",
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Token count of the chunk content.",
    )
    character_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Character count of the chunk text.",
    )
    checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="SHA-256 cryptographic digest of the chunk text.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Timestamp in UTC when the chunk record was created.",
    )

    # Relationships
    document: Mapped[KnowledgeDocument] = relationship(
        "KnowledgeDocument",
        back_populates="chunks",
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "ix_knowledge_chunks_doc_index", "document_id", "chunk_index", unique=True
        ),
    )

    def __init__(
        self,
        *,
        document_id: uuid.UUID,
        chunk_index: int,
        text: str,
        page_number: int | None = None,
        heading: str | None = None,
        token_count: int = 0,
        character_count: int | None = None,
        checksum: str | None = None,
        id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        char_cnt = character_count if character_count is not None else len(text)
        chk = checksum or hashlib.sha256(text.encode("utf-8")).hexdigest()

        super().__init__(
            document_id=document_id,
            chunk_index=chunk_index,
            text=text,
            page_number=page_number,
            heading=heading,
            token_count=token_count,
            character_count=char_cnt,
            checksum=chk,
            id=id or uuid.uuid4(),
            **kwargs,
        )

    def __repr__(self) -> str:
        return (
            f"<KnowledgeChunk id={self.id} doc_id={self.document_id} "
            f"index={self.chunk_index} tokens={self.token_count}>"
        )
