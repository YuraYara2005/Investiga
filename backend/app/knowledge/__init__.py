"""Knowledge Management Domain Package for Investiga.

This package provides domain models, relational repositories, Pydantic schemas,
and application services for ingesting and organizing operational documentation.
"""

from app.knowledge.models import (
    DocumentCategory,
    EmbeddingStatus,
    KnowledgeDocument,
    ProcessingStatus,
)
from app.knowledge.repositories import KnowledgeRepository
from app.knowledge.schemas import (
    KnowledgeDocumentListResponse,
    KnowledgeDocumentResponse,
    UpdateDocumentRequest,
    UploadDocumentRequest,
)
from app.knowledge.services import KnowledgeService

__all__ = [
    "DocumentCategory",
    "EmbeddingStatus",
    "KnowledgeDocument",
    "KnowledgeDocumentListResponse",
    "KnowledgeDocumentResponse",
    "KnowledgeRepository",
    "KnowledgeService",
    "ProcessingStatus",
    "UpdateDocumentRequest",
    "UploadDocumentRequest",
]
