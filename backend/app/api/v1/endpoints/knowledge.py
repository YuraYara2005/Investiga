"""Knowledge Management API Endpoints for Investiga.

Provides HTTP controllers for secure file ingestion, document listing,
metadata retrieval, search, and soft deletion with physical storage cleanup.
"""

import uuid
from pathlib import PurePath
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
    status,
)

from app.api.dependencies import (
    get_current_active_user,
    get_knowledge_service,
    get_storage_service,
)
from app.auth.models import User
from app.exceptions.domain import ConflictException, ValidationException
from app.knowledge.models import (
    DocumentCategory,
    EmbeddingStatus,
    ProcessingStatus,
)
from app.knowledge.schemas import (
    KnowledgeDocumentListResponse,
    KnowledgeDocumentResponse,
    UploadDocumentRequest,
)
from app.knowledge.services import KnowledgeService
from app.storage.storage_service import StorageService

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])


@router.post(
    "/upload",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a knowledge document",
    description="Validates, stores physical file payload, enforces checksum uniqueness, and indexes metadata.",
)
async def upload_document(
    file: Annotated[UploadFile, File(description="Multipart file payload")],
    title: Annotated[str | None, Form(description="Document title")] = None,
    description: Annotated[
        str | None, Form(description="Detailed document summary")
    ] = None,
    category: Annotated[
        DocumentCategory,
        Form(description="Operational classification category"),
    ] = DocumentCategory.OTHER,
    tags: Annotated[
        str | None,
        Form(description="Comma-separated list of categorization tags"),
    ] = None,
    language: Annotated[
        str, Form(description="Primary document ISO language code")
    ] = "en",
    current_user: User = Depends(get_current_active_user),
    storage_service: StorageService = Depends(get_storage_service),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeDocumentResponse:
    """Handle multipart file upload, validate storage constraints, and persist document record."""
    if not file.filename:
        raise ValidationException(
            message="Uploaded file must include a valid filename.",
            details={"filename": file.filename},
        )

    # Read binary payload from stream
    content = await file.read()

    # 1. Validate and store file on disk/storage provider
    stored_metadata = await storage_service.store_file(
        filename=file.filename,
        content=content,
        client_mime_type=file.content_type,
    )

    # 2. Derive title from filename if not explicitly provided
    resolved_title = (
        title.strip()
        if title and title.strip()
        else PurePath(stored_metadata.original_filename).stem
    )

    # 3. Parse optional tags
    parsed_tags: list[str] = []
    if tags and tags.strip():
        parsed_tags = [t.strip() for t in tags.split(",") if t.strip()]

    # 4. Construct ingestion request
    doc_request = UploadDocumentRequest(
        title=resolved_title,
        description=description.strip() if description else None,
        original_filename=stored_metadata.original_filename,
        stored_filename=stored_metadata.stored_filename,
        file_extension=stored_metadata.file_extension,
        mime_type=stored_metadata.mime_type,
        file_size=stored_metadata.file_size,
        checksum=stored_metadata.checksum,
        storage_path=stored_metadata.storage_path,
        category=category,
        tags=parsed_tags,
        language=language,
    )

    # 5. Persist document metadata in database with duplicate checksum rollback guard
    try:
        document_response = await knowledge_service.create_document(
            request=doc_request,
            user_id=current_user.id,
        )
    except ConflictException:
        # Clean up orphan physical file if duplicate checksum rejected by database
        await storage_service.delete_file(stored_metadata.stored_filename)
        raise

    return document_response


@router.get(
    "",
    response_model=KnowledgeDocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List or search knowledge documents",
    description="Retrieve paginated list of knowledge documents with multi-field filtering and search capabilities.",
)
async def list_documents(
    skip: Annotated[int, Query(ge=0, description="Offset")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Page limit")] = 50,
    category: Annotated[
        DocumentCategory | None, Query(description="Category filter")
    ] = None,
    processing_status: Annotated[
        ProcessingStatus | None,
        Query(description="Processing status filter"),
    ] = None,
    embedding_status: Annotated[
        EmbeddingStatus | None,
        Query(description="Embedding status filter"),
    ] = None,
    search: Annotated[
        str | None,
        Query(description="Substring search across title, description, and filename"),
    ] = None,
    sort_by: Annotated[str, Query(description="Sort attribute")] = "created_at",
    sort_desc: Annotated[bool, Query(description="Descending order if True")] = True,
    current_user: User = Depends(get_current_active_user),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeDocumentListResponse:
    """Query knowledge documents collection."""
    if search and search.strip():
        return await knowledge_service.search_documents(
            query=search.strip(),
            skip=skip,
            limit=limit,
            category=category,
        )

    return await knowledge_service.list_documents(
        skip=skip,
        limit=limit,
        category=category,
        processing_status=processing_status,
        embedding_status=embedding_status,
        sort_by=sort_by,
        sort_desc=sort_desc,
    )


@router.get(
    "/{id}",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get knowledge document by ID",
    description="Fetch single document metadata record by unique UUID identifier.",
)
async def get_document(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeDocumentResponse:
    """Retrieve document metadata by ID."""
    return await knowledge_service.get_document(id)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete knowledge document",
    description="Soft-deletes metadata from database and purges physical file from storage.",
)
async def delete_document(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> None:
    """Soft delete document record and purge physical storage file."""
    await knowledge_service.delete_document(id)
