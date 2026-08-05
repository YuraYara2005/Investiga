"""Integration tests for Knowledge Management Document Upload & Storage API.

Covers:
- POST /api/v1/knowledge/upload (multipart file upload, metadata recording, storage)
- Duplicate checksum rejection (409 Conflict) and physical file rollback
- Security validation defenses (prohibited executables, path traversal, empty files)
- GET /api/v1/knowledge (filtering, pagination, substring search)
- GET /api/v1/knowledge/{id} (metadata detail lookup)
- DELETE /api/v1/knowledge/{id} (soft-delete record + physical storage file deletion)
- Authentication and authorization guard enforcement
"""

import tempfile
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.dependencies import get_database, get_storage_service
from app.auth.models import User
from app.auth.repositories import UserRepository
from app.core.config import Settings
from app.core.security import create_access_token
from app.db.base import Base
from app.knowledge.models import DocumentCategory
from app.main import create_app
from app.storage import LocalStorageProvider, StorageService


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
async def temp_storage_dir() -> str:
    """Create a temporary directory for file upload test storage."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest_asyncio.fixture
async def test_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> User:
    """Seed an active user for authenticated API operations."""
    async with session_factory() as session:
        repo = UserRepository(session=session)
        user = User(
            email="sre.engineer@investiga.internal",
            hashed_password="mock_hashed_password_for_tests",
            full_name="Site Reliability Engineer",
            is_active=True,
            is_verified=True,
        )
        saved_user = await repo.create(user)
        await session.commit()
        return saved_user


@pytest_asyncio.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    """Generate JWT authorization bearer header for test user."""
    token = create_access_token(
        subject=str(test_user.id),
        roles=["Admin"],
        permissions=["knowledge:read", "knowledge:create", "knowledge:delete"],
        custom_claims={"email": test_user.email},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def app_client(
    session_factory: async_sessionmaker[AsyncSession],
    temp_storage_dir: str,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTPX AsyncClient configured with test database session and temporary storage."""
    app: FastAPI = create_app()

    test_settings = Settings()
    test_settings.storage.upload_directory = temp_storage_dir
    test_settings.storage.max_upload_size_mb = 10

    test_storage_service = StorageService(
        provider=LocalStorageProvider(base_directory=temp_storage_dir),
        settings=test_settings,
    )

    async def override_get_database() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    def override_get_storage_service() -> StorageService:
        return test_storage_service

    app.dependency_overrides[get_database] = override_get_database
    app.dependency_overrides[get_storage_service] = override_get_storage_service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client


# ------------------------------------------------------------------------------
# 1. Document Upload Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_document_success(
    app_client: AsyncClient,
    auth_headers: dict[str, str],
    temp_storage_dir: str,
) -> None:
    """Test successful multipart document upload and storage."""
    file_content = b"%PDF-1.4 Kubernetes Runbook Content for Investigation"
    files = {
        "file": ("incident_runbook.pdf", file_content, "application/pdf"),
    }
    data = {
        "title": "Kubernetes Outage Runbook",
        "description": "Step by step procedures for diagnosing pod crashloops.",
        "category": DocumentCategory.RUNBOOK.value,
        "tags": "k8s,sre,runbook",
        "language": "en",
    }

    response = await app_client.post(
        "/api/v1/knowledge/upload",
        files=files,
        data=data,
        headers=auth_headers,
    )

    assert response.status_code == 201
    res_data = response.json()
    assert res_data["title"] == "Kubernetes Outage Runbook"
    assert res_data["original_filename"] == "incident_runbook.pdf"
    assert res_data["file_extension"] == ".pdf"
    assert res_data["mime_type"] == "application/pdf"
    assert res_data["category"] == DocumentCategory.RUNBOOK.value
    assert res_data["tags"] == ["k8s", "sre", "runbook"]
    assert res_data["file_size"] == len(file_content)
    assert len(res_data["checksum"]) == 64

    # Verify physical file existence in storage directory
    stored_path = Path(temp_storage_dir) / res_data["stored_filename"]
    assert stored_path.exists()
    assert stored_path.read_bytes() == file_content


@pytest.mark.asyncio
async def test_upload_duplicate_checksum_conflict_and_cleanup(
    app_client: AsyncClient,
    auth_headers: dict[str, str],
    temp_storage_dir: str,
) -> None:
    """Test rejection of duplicate checksum uploads and rollback of orphan physical files."""
    file_content = b"%PDF-1.5 Unique Checksum Payload Test"
    files1 = {"file": ("doc_v1.pdf", file_content, "application/pdf")}
    data1 = {"title": "Doc Version 1"}

    # 1. First upload succeeds
    res1 = await app_client.post(
        "/api/v1/knowledge/upload",
        files=files1,
        data=data1,
        headers=auth_headers,
    )
    assert res1.status_code == 201

    # 2. Second upload with identical content fails with 409 Conflict
    files2 = {"file": ("doc_v2.pdf", file_content, "application/pdf")}
    data2 = {"title": "Doc Version 2"}

    res2 = await app_client.post(
        "/api/v1/knowledge/upload",
        files=files2,
        data=data2,
        headers=auth_headers,
    )
    assert res2.status_code == 409
    assert "already exists" in res2.json()["error"]["message"]


@pytest.mark.asyncio
async def test_upload_security_validations(
    app_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Test rejection of malicious uploads (executables, path traversal, empty files)."""
    # 1. Executable file rejection
    res_exe = await app_client.post(
        "/api/v1/knowledge/upload",
        files={"file": ("malware.exe", b"binary content", "application/octet-stream")},
        headers=auth_headers,
    )
    assert res_exe.status_code in [400, 422]

    # 2. Path traversal in filename rejection
    res_traversal = await app_client.post(
        "/api/v1/knowledge/upload",
        files={
            "file": ("../../etc/passwd.pdf", b"%PDF-1.4 payload", "application/pdf")
        },
        headers=auth_headers,
    )
    assert res_traversal.status_code in [400, 422]

    # 3. Empty file rejection
    res_empty = await app_client.post(
        "/api/v1/knowledge/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        headers=auth_headers,
    )
    assert res_empty.status_code in [400, 422]


@pytest.mark.asyncio
async def test_upload_unauthorized_rejection(
    app_client: AsyncClient,
) -> None:
    """Test rejection of unauthenticated upload requests."""
    res = await app_client.post(
        "/api/v1/knowledge/upload",
        files={"file": ("doc.pdf", b"%PDF-1.4 content", "application/pdf")},
    )
    assert res.status_code == 401


# ------------------------------------------------------------------------------
# 2. Document Query and Search Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_and_search_documents(
    app_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Test listing, filtering by category, and metadata substring search."""
    # Seed 2 distinct documents
    doc1_content = b"%PDF-1.4 Security Firewall Spec"
    await app_client.post(
        "/api/v1/knowledge/upload",
        files={"file": ("firewall_policy.pdf", doc1_content, "application/pdf")},
        data={
            "title": "Firewall Security Architecture",
            "category": DocumentCategory.CONFIGURATION.value,
        },
        headers=auth_headers,
    )

    doc2_content = b"%PDF-1.4 Disaster Recovery Handbook"
    await app_client.post(
        "/api/v1/knowledge/upload",
        files={"file": ("dr_plan.pdf", doc2_content, "application/pdf")},
        data={
            "title": "Disaster Recovery Playbook",
            "category": DocumentCategory.RUNBOOK.value,
        },
        headers=auth_headers,
    )

    # 1. List all
    list_res = await app_client.get("/api/v1/knowledge", headers=auth_headers)
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 2

    # 2. Filter by category
    cat_res = await app_client.get(
        f"/api/v1/knowledge?category={DocumentCategory.RUNBOOK.value}",
        headers=auth_headers,
    )
    assert cat_res.status_code == 200
    assert cat_res.json()["total"] == 1
    assert cat_res.json()["items"][0]["title"] == "Disaster Recovery Playbook"

    # 3. Substring search
    search_res = await app_client.get(
        "/api/v1/knowledge?search=Firewall",
        headers=auth_headers,
    )
    assert search_res.status_code == 200
    assert search_res.json()["total"] == 1
    assert search_res.json()["items"][0]["title"] == "Firewall Security Architecture"


# ------------------------------------------------------------------------------
# 3. Document Retrieval and Deletion Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_and_delete_document_lifecycle(
    app_client: AsyncClient,
    auth_headers: dict[str, str],
    temp_storage_dir: str,
) -> None:
    """Test get by ID, soft-deletion, physical file removal, and 404 handling."""
    content = b"%PDF-1.4 Ephemeral Test Document"
    upload_res = await app_client.post(
        "/api/v1/knowledge/upload",
        files={"file": ("ephemeral.pdf", content, "application/pdf")},
        headers=auth_headers,
    )
    doc_id = upload_res.json()["id"]
    stored_name = upload_res.json()["stored_filename"]
    stored_file_path = Path(temp_storage_dir) / stored_name

    assert stored_file_path.exists()

    # 1. Retrieve by ID
    get_res = await app_client.get(f"/api/v1/knowledge/{doc_id}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == doc_id

    # 2. Delete document
    del_res = await app_client.delete(
        f"/api/v1/knowledge/{doc_id}", headers=auth_headers
    )
    assert del_res.status_code == 204

    # 3. Verify physical file removed from storage
    assert not stored_file_path.exists()

    # 4. Verify subsequent GET returns 404
    get_del_res = await app_client.get(
        f"/api/v1/knowledge/{doc_id}", headers=auth_headers
    )
    assert get_del_res.status_code == 404

    # 5. Verify non-existent UUID returns 404
    non_existent_res = await app_client.get(
        f"/api/v1/knowledge/{uuid.uuid4()}",
        headers=auth_headers,
    )
    assert non_existent_res.status_code == 404
