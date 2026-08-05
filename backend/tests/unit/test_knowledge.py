"""Unit and Integration Tests for Knowledge Management Foundation.

Covers:
- KnowledgeDocument model instantiation, attributes, and relationships
- DocumentCategory, ProcessingStatus, and EmbeddingStatus enums
- KnowledgeRepository CRUD, search, checksum verification, filtering, and soft delete
- KnowledgeService validation, duplicate checksum conflict, and orchestration
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.auth.models import User
from app.auth.repositories import UserRepository
from app.db.base import Base
from app.exceptions.domain import ConflictException, NotFoundException
from app.knowledge.models import (
    DocumentCategory,
    EmbeddingStatus,
    KnowledgeDocument,
    ProcessingStatus,
)
from app.knowledge.repositories import KnowledgeRepository
from app.knowledge.schemas import (
    UpdateDocumentRequest,
    UploadDocumentRequest,
)
from app.knowledge.services import KnowledgeService


@pytest_asyncio.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Provide an in-memory SQLite async database engine initialized with relational schema."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(
    test_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Provide an async session factory bound to the isolated test database."""
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest_asyncio.fixture
async def test_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> User:
    """Seed a test user to serve as document uploader."""
    async with session_factory() as session:
        repo = UserRepository(session=session)
        user = User(
            email="doc.author@investiga.internal",
            hashed_password="mock_hash_for_tests",
            full_name="Knowledge Author",
            is_active=True,
            is_verified=True,
        )
        saved = await repo.create(user)
        await session.commit()
        return saved


# ------------------------------------------------------------------------------
# 1. Domain Model and Enum Tests
# ------------------------------------------------------------------------------


def test_knowledge_enums() -> None:
    """Verify enum members and values."""
    assert DocumentCategory.RUNBOOK.value == "RUNBOOK"
    assert DocumentCategory.INCIDENT_REPORT.value == "INCIDENT_REPORT"
    assert DocumentCategory.MANUAL.value == "MANUAL"
    assert DocumentCategory.CONFIGURATION.value == "CONFIGURATION"
    assert DocumentCategory.POLICY.value == "POLICY"
    assert DocumentCategory.OTHER.value == "OTHER"

    assert ProcessingStatus.UPLOADED.value == "UPLOADED"
    assert ProcessingStatus.VALIDATING.value == "VALIDATING"
    assert ProcessingStatus.PROCESSING.value == "PROCESSING"
    assert ProcessingStatus.READY.value == "READY"
    assert ProcessingStatus.FAILED.value == "FAILED"

    assert EmbeddingStatus.NOT_STARTED.value == "NOT_STARTED"
    assert EmbeddingStatus.QUEUED.value == "QUEUED"
    assert EmbeddingStatus.EMBEDDED.value == "EMBEDDED"
    assert EmbeddingStatus.FAILED.value == "FAILED"


def test_knowledge_document_model_instantiation() -> None:
    """Test KnowledgeDocument entity initialization and default values."""
    user_id = uuid.uuid4()
    doc = KnowledgeDocument(
        title="Production Incident Runbook",
        original_filename="runbook.pdf",
        stored_filename="stored_runbook_123.pdf",
        file_extension=".pdf",
        mime_type="application/pdf",
        file_size=1048576,
        checksum="a" * 64,
        storage_path="/var/storage/runbook.pdf",
        uploaded_by=user_id,
        category=DocumentCategory.RUNBOOK,
        tags=["sre", "incident"],
    )

    assert doc.title == "Production Incident Runbook"
    assert doc.category == DocumentCategory.RUNBOOK
    assert doc.processing_status == ProcessingStatus.UPLOADED
    assert doc.embedding_status == EmbeddingStatus.NOT_STARTED
    assert doc.tags == ["sre", "incident"]
    assert doc.version == 1
    assert doc.is_deleted is False
    assert "Production Incident Runbook" in repr(doc)


# ------------------------------------------------------------------------------
# 2. Repository Layer Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_knowledge_repository_crud(
    session_factory: async_sessionmaker[AsyncSession],
    test_user: User,
) -> None:
    """Test repository create, get, checksum query, update, and soft delete operations."""
    async with session_factory() as session:
        repo = KnowledgeRepository(session=session)

        checksum = "b" * 64
        doc = KnowledgeDocument(
            title="Database Disaster Recovery",
            description="Procedures for restoring PostgreSQL cluster from WAL archives.",
            original_filename="dr_guide.pdf",
            stored_filename="stored_dr_guide_001.pdf",
            file_extension=".pdf",
            mime_type="application/pdf",
            file_size=512000,
            checksum=checksum,
            storage_path="s3://investiga/dr_guide.pdf",
            uploaded_by=test_user.id,
            category=DocumentCategory.RUNBOOK,
            tags=["postgres", "backup", "dr"],
        )

        # 1. Create
        created = await repo.create(doc)
        await session.commit()
        assert created.id is not None

        # 2. Checksum validation
        assert await repo.exists_checksum(checksum) is True
        assert await repo.exists_checksum("c" * 64) is False

        fetched_by_checksum = await repo.get_by_checksum(checksum)
        assert fetched_by_checksum is not None
        assert fetched_by_checksum.id == created.id

        # 3. Get by ID
        fetched = await repo.get_by_id(created.id)
        assert fetched is not None
        assert fetched.title == "Database Disaster Recovery"

        # 4. Update
        fetched.title = "PostgreSQL Disaster Recovery V2"
        fetched.processing_status = ProcessingStatus.READY
        updated = await repo.update(fetched)
        await session.commit()
        assert updated.title == "PostgreSQL Disaster Recovery V2"
        assert updated.processing_status == ProcessingStatus.READY

        # 5. Soft delete
        deleted = await repo.soft_delete(created.id)
        await session.commit()
        assert deleted is True

        # Ensure soft-deleted document is filtered out by default
        assert await repo.get_by_id(created.id) is None
        assert await repo.exists_checksum(checksum) is False
        assert await repo.get_by_id(created.id, include_deleted=True) is not None


@pytest.mark.asyncio
async def test_knowledge_repository_filtering_and_search(
    session_factory: async_sessionmaker[AsyncSession],
    test_user: User,
) -> None:
    """Test repository listing, category filtering, search, and counting."""
    async with session_factory() as session:
        repo = KnowledgeRepository(session=session)

        # Seed multiple documents
        docs = [
            KnowledgeDocument(
                title="Kubernetes Cluster Manual",
                description="Cluster setup and node provisioning.",
                original_filename="k8s_manual.docx",
                stored_filename="stored_k8s_manual.docx",
                file_extension=".docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                file_size=204800,
                checksum="1" * 64,
                storage_path="/storage/k8s_manual.docx",
                uploaded_by=test_user.id,
                category=DocumentCategory.MANUAL,
            ),
            KnowledgeDocument(
                title="Security Incident Post-Mortem #402",
                description="Analysis of unauthorized access attempt on gateway.",
                original_filename="incident_402.pdf",
                stored_filename="stored_incident_402.pdf",
                file_extension=".pdf",
                mime_type="application/pdf",
                file_size=102400,
                checksum="2" * 64,
                storage_path="/storage/incident_402.pdf",
                uploaded_by=test_user.id,
                category=DocumentCategory.INCIDENT_REPORT,
            ),
            KnowledgeDocument(
                title="IAM Access Policy Matrix",
                description="RBAC rules and least privilege configuration.",
                original_filename="iam_policy.md",
                stored_filename="stored_iam_policy.md",
                file_extension=".md",
                mime_type="text/markdown",
                file_size=4096,
                checksum="3" * 64,
                storage_path="/storage/iam_policy.md",
                uploaded_by=test_user.id,
                category=DocumentCategory.POLICY,
            ),
        ]

        for d in docs:
            await repo.create(d)
        await session.commit()

        # 1. Total count
        total_count = await repo.count_documents()
        assert total_count == 3

        # 2. Filter by category
        manuals = await repo.list_documents(category=DocumentCategory.MANUAL)
        assert len(manuals) == 1
        assert manuals[0].title == "Kubernetes Cluster Manual"

        # 3. Search metadata
        search_results = await repo.search_metadata("gateway")
        assert len(search_results) == 1
        assert search_results[0].title == "Security Incident Post-Mortem #402"

        # 4. Search across titles
        search_all = await repo.search_metadata("Incident")
        assert len(search_all) == 1


# ------------------------------------------------------------------------------
# 3. Service Layer Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_knowledge_service_create_and_duplicate_prevention(
    session_factory: async_sessionmaker[AsyncSession],
    test_user: User,
) -> None:
    """Test service document creation and duplicate checksum enforcement."""
    async with session_factory() as session:
        service = KnowledgeService(session=session)

        req = UploadDocumentRequest(
            title="Firewall Architecture Spec",
            description="Edge firewall rules and DMZ topologies.",
            original_filename="firewall_spec.pdf",
            stored_filename="stored_firewall_spec.pdf",
            file_extension=".pdf",
            mime_type="application/pdf",
            file_size=819200,
            checksum="4" * 64,
            storage_path="/storage/firewall_spec.pdf",
            category=DocumentCategory.CONFIGURATION,
            tags=["network", "firewall"],
        )

        # Successful creation
        created_response = await service.create_document(req, user_id=test_user.id)
        await session.commit()

        assert created_response.title == "Firewall Architecture Spec"
        assert created_response.category == DocumentCategory.CONFIGURATION
        assert created_response.uploaded_by == test_user.id

        # Duplicate checksum rejection
        with pytest.raises(ConflictException) as exc_info:
            await service.create_document(req, user_id=test_user.id)

        assert "already exists" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_knowledge_service_lifecycle_and_exceptions(
    session_factory: async_sessionmaker[AsyncSession],
    test_user: User,
) -> None:
    """Test service get, update, delete, search, and NotFound exception handling."""
    async with session_factory() as session:
        service = KnowledgeService(session=session)

        # 1. Create document
        req = UploadDocumentRequest(
            title="Service Mesh Configuration",
            description="Istio mTLS configuration guidelines.",
            original_filename="istio_cfg.yaml",
            stored_filename="stored_istio_cfg.yaml",
            file_extension=".yaml",
            mime_type="application/x-yaml",
            file_size=16384,
            checksum="5" * 64,
            storage_path="/storage/istio_cfg.yaml",
            category=DocumentCategory.CONFIGURATION,
        )
        created = await service.create_document(req, user_id=test_user.id)
        await session.commit()

        # 2. Get document
        retrieved = await service.get_document(created.id)
        assert retrieved.id == created.id
        assert retrieved.title == "Service Mesh Configuration"

        # 3. Update document
        update_req = UpdateDocumentRequest(
            title="Enterprise Service Mesh Config V2",
            processing_status=ProcessingStatus.READY,
            embedding_status=EmbeddingStatus.QUEUED,
        )
        updated = await service.update_document(created.id, update_req)
        await session.commit()

        assert updated.title == "Enterprise Service Mesh Config V2"
        assert updated.processing_status == ProcessingStatus.READY
        assert updated.embedding_status == EmbeddingStatus.QUEUED

        # 4. List and search via service
        list_res = await service.list_documents(category=DocumentCategory.CONFIGURATION)
        assert list_res.total == 1
        assert len(list_res.items) == 1

        search_res = await service.search_documents("Mesh")
        assert search_res.total == 1
        assert search_res.items[0].id == created.id

        # 5. Delete document
        delete_success = await service.delete_document(created.id)
        await session.commit()
        assert delete_success is True

        # 6. Verify NotFoundException on deleted doc
        with pytest.raises(NotFoundException):
            await service.get_document(created.id)

        # 7. Verify NotFoundException on non-existent UUID
        with pytest.raises(NotFoundException):
            await service.get_document(uuid.uuid4())
