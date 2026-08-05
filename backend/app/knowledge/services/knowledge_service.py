"""Knowledge Management Service for Investiga.

This module encapsulates business logic for operational document registration,
checksum validation, metadata search, soft-deletion, and lifecycle management.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.exceptions.domain import ConflictException, NotFoundException
from app.knowledge.models import (
    DocumentCategory,
    EmbeddingStatus,
    KnowledgeDocument,
    ProcessingStatus,
)
from app.knowledge.repositories.knowledge_repository import KnowledgeRepository
from app.knowledge.schemas.document import (
    KnowledgeDocumentListResponse,
    KnowledgeDocumentResponse,
    UpdateDocumentRequest,
    UploadDocumentRequest,
)
from app.storage.storage_service import StorageService

logger = get_logger(__name__)


class KnowledgeService:
    """Application service coordinating knowledge document management operations."""

    def __init__(
        self,
        session: AsyncSession,
        repository: KnowledgeRepository | None = None,
        storage_service: StorageService | None = None,
    ) -> None:
        self._session = session
        self._repo = repository or KnowledgeRepository(session=session)
        self._storage_service = storage_service

    async def validate_duplicate_checksum(self, checksum: str) -> None:
        """Enforce uniqueness invariant preventing duplicate document uploads.

        Args:
            checksum: SHA-256 cryptographic digest.

        Raises:
            ConflictException: If a document with identical checksum already exists.
        """
        exists = await self._repo.exists_checksum(checksum=checksum)
        if exists:
            logger.warning(
                "knowledge_document_duplicate_rejected",
                checksum=checksum,
            )
            raise ConflictException(
                message=f"A document with identical SHA-256 checksum '{checksum}' already exists in the knowledge base.",
                details={"checksum": checksum},
            )

    async def create_document(
        self,
        request: UploadDocumentRequest,
        user_id: uuid.UUID,
    ) -> KnowledgeDocumentResponse:
        """Register a new knowledge document after validating checksum uniqueness.

        Args:
            request: Validated document metadata request DTO.
            user_id: Principal UUID of the uploading user.

        Returns:
            KnowledgeDocumentResponse: Public response representation of the document.

        Raises:
            ConflictException: If duplicate checksum is detected.
        """
        await self.validate_duplicate_checksum(request.checksum)

        document = KnowledgeDocument(
            title=request.title,
            description=request.description,
            original_filename=request.original_filename,
            stored_filename=request.stored_filename,
            file_extension=request.file_extension,
            mime_type=request.mime_type,
            file_size=request.file_size,
            language=request.language,
            category=request.category,
            tags=request.tags,
            version=request.version,
            checksum=request.checksum,
            storage_path=request.storage_path,
            uploaded_by=user_id,
            processing_status=ProcessingStatus.UPLOADED,
            embedding_status=EmbeddingStatus.NOT_STARTED,
        )

        persisted = await self._repo.create(document)
        await self._session.commit()

        logger.info(
            "knowledge_document_created",
            document_id=str(persisted.id),
            title=persisted.title,
            category=persisted.category.value,
            uploaded_by=str(user_id),
            checksum=persisted.checksum,
        )

        return KnowledgeDocumentResponse.model_validate(persisted)

    async def get_document(self, document_id: uuid.UUID) -> KnowledgeDocumentResponse:
        """Retrieve a knowledge document by ID.

        Args:
            document_id: UUID primary key.

        Returns:
            KnowledgeDocumentResponse: Response DTO.

        Raises:
            NotFoundException: If the document does not exist or is soft-deleted.
        """
        document = await self._repo.get_by_id(document_id)
        if document is None or document.is_deleted:
            raise NotFoundException(
                resource_name="KnowledgeDocument",
                identifier=str(document_id),
            )

        return KnowledgeDocumentResponse.model_validate(document)

    async def update_document(
        self,
        document_id: uuid.UUID,
        request: UpdateDocumentRequest,
    ) -> KnowledgeDocumentResponse:
        """Update mutable metadata and pipeline statuses for an existing document.

        Args:
            document_id: Target document primary key.
            request: Partial update request DTO.

        Returns:
            KnowledgeDocumentResponse: Refreshed document response DTO.

        Raises:
            NotFoundException: If document is not found.
        """
        document = await self._repo.get_by_id(document_id)
        if document is None or document.is_deleted:
            raise NotFoundException(
                resource_name="KnowledgeDocument",
                identifier=str(document_id),
            )

        if request.title is not None:
            document.title = request.title
        if request.description is not None:
            document.description = request.description
        if request.language is not None:
            document.language = request.language
        if request.category is not None:
            document.category = request.category
        if request.tags is not None:
            document.tags = request.tags
        if request.processing_status is not None:
            document.processing_status = request.processing_status
        if request.embedding_status is not None:
            document.embedding_status = request.embedding_status

        updated = await self._repo.update(document)
        await self._session.commit()

        logger.info(
            "knowledge_document_updated",
            document_id=str(updated.id),
            title=updated.title,
            processing_status=updated.processing_status.value,
            embedding_status=updated.embedding_status.value,
        )

        return KnowledgeDocumentResponse.model_validate(updated)

    async def delete_document(self, document_id: uuid.UUID) -> bool:
        """Soft-delete a knowledge document from the platform.

        Args:
            document_id: Target document primary key.

        Returns:
            bool: True on successful deletion.

        Raises:
            NotFoundException: If document is not found or already deleted.
        """
        document = await self._repo.get_by_id(document_id)
        if document is None or document.is_deleted:
            raise NotFoundException(
                resource_name="KnowledgeDocument",
                identifier=str(document_id),
            )

        # Remove physical file from storage provider
        if self._storage_service and document.stored_filename:
            await self._storage_service.delete_file(document.stored_filename)

        deleted = await self._repo.soft_delete(document_id)
        await self._session.commit()

        logger.info(
            "knowledge_document_deleted",
            document_id=str(document_id),
            stored_filename=document.stored_filename,
        )

        return deleted

    async def list_documents(
        self,
        skip: int = 0,
        limit: int = 50,
        category: DocumentCategory | None = None,
        processing_status: ProcessingStatus | None = None,
        embedding_status: EmbeddingStatus | None = None,
        uploaded_by: uuid.UUID | None = None,
        sort_by: str = "created_at",
        sort_desc: bool = True,
    ) -> KnowledgeDocumentListResponse:
        """List documents matching filtering and pagination parameters.

        Args:
            skip: Offset.
            limit: Page size.
            category: Optional category filter.
            processing_status: Optional processing status filter.
            embedding_status: Optional embedding status filter.
            uploaded_by: Optional uploader filter.
            sort_by: Target model column name.
            sort_desc: Sort descending if True.

        Returns:
            KnowledgeDocumentListResponse: Paginated results envelope.
        """
        documents = await self._repo.list_documents(
            skip=skip,
            limit=limit,
            category=category,
            processing_status=processing_status,
            embedding_status=embedding_status,
            uploaded_by=uploaded_by,
            sort_by=sort_by,
            sort_desc=sort_desc,
        )

        total = await self._repo.count_documents(
            category=category,
            processing_status=processing_status,
            embedding_status=embedding_status,
            uploaded_by=uploaded_by,
        )

        return KnowledgeDocumentListResponse(
            items=[KnowledgeDocumentResponse.model_validate(d) for d in documents],
            total=total,
            skip=skip,
            limit=limit,
        )

    async def search_documents(
        self,
        query: str,
        skip: int = 0,
        limit: int = 50,
        category: DocumentCategory | None = None,
    ) -> KnowledgeDocumentListResponse:
        """Search documents by metadata substring matches across title/desc/filename.

        Args:
            query: Substring search term.
            skip: Offset.
            limit: Limit.
            category: Optional category filter.

        Returns:
            KnowledgeDocumentListResponse: Search results envelope.
        """
        documents = await self._repo.search_metadata(
            query=query,
            skip=skip,
            limit=limit,
            category=category,
        )

        total = await self._repo.count_documents(
            search_query=query,
            category=category,
        )

        return KnowledgeDocumentListResponse(
            items=[KnowledgeDocumentResponse.model_validate(d) for d in documents],
            total=total,
            skip=skip,
            limit=limit,
        )
