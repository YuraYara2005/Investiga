"""Unit and Integration tests for Identity Domain Repositories using an async in-memory database."""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.auth.models import Permission, Role, User
from app.auth.repositories import (
    PermissionRepository,
    RoleRepository,
    UserRepository,
)
from app.db.base import Base


@pytest_asyncio.fixture
async def async_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an isolated in-memory SQLite async engine for repository testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    async_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean AsyncSession per test."""
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest.mark.asyncio
async def test_user_repository_crud_operations(db_session: AsyncSession) -> None:
    repo = UserRepository(session=db_session)

    # 1. Create User
    new_user = User(
        email="analyst.lead@investiga.internal",
        hashed_password="$argon2id$v=19$m=65536,t=3,p=4$fakehash",
        full_name="Lead Analyst",
    )
    created = await repo.create(new_user)
    assert created.id is not None
    assert created.email == "analyst.lead@investiga.internal"

    # 2. Get By ID
    retrieved = await repo.get_by_id(created.id)
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.full_name == "Lead Analyst"

    # 3. Exists & Count
    assert await repo.exists(created.id) is True
    assert await repo.count() == 1

    # 4. Update
    retrieved.full_name = "Principal Incident Analyst"
    updated = await repo.update(retrieved)
    assert updated.full_name == "Principal Incident Analyst"


@pytest.mark.asyncio
async def test_user_repository_email_queries(db_session: AsyncSession) -> None:
    repo = UserRepository(session=db_session)

    user = User(
        email="Incident.Commander@investiga.internal",
        hashed_password="hash",
        full_name="Commander One",
    )
    await repo.create(user)

    # Case-insensitive lookup
    found = await repo.get_by_email("incident.commander@investiga.internal")
    assert found is not None
    assert found.id == user.id

    # Email exists check
    assert await repo.email_exists("incident.commander@investiga.internal") is True
    assert await repo.email_exists("unknown@investiga.internal") is False


@pytest.mark.asyncio
async def test_user_repository_eager_loading_roles_and_permissions(
    db_session: AsyncSession,
) -> None:
    user_repo = UserRepository(session=db_session)
    role_repo = RoleRepository(session=db_session)
    perm_repo = PermissionRepository(session=db_session)

    # 1. Create permissions
    p1 = Permission(
        code="investigations:create", resource="investigations", action="create"
    )
    p2 = Permission(
        code="investigations:read", resource="investigations", action="read"
    )
    await perm_repo.bulk_create([p1, p2])

    # 2. Create role with permissions
    role = Role(name="investigator", display_name="Investigator")
    role.permissions = [p1, p2]
    await role_repo.create(role)

    # 3. Create user with role
    user = User(
        email="eager.load@investiga.internal",
        hashed_password="hash",
        full_name="Eager User",
    )
    user.roles = [role]
    await user_repo.create(user)

    # 4. Fetch user with full eager loading
    fetched = await user_repo.get_by_email_with_roles_and_permissions(
        "eager.load@investiga.internal"
    )
    assert fetched is not None
    assert len(fetched.roles) == 1
    assert fetched.roles[0].name == "investigator"
    assert len(fetched.roles[0].permissions) == 2
    assert fetched.permission_codes == {"investigations:create", "investigations:read"}


@pytest.mark.asyncio
async def test_user_repository_soft_delete(db_session: AsyncSession) -> None:
    repo = UserRepository(session=db_session)

    user = User(
        email="delete.me@investiga.internal",
        hashed_password="hash",
        full_name="Delete Candidate",
    )
    created = await repo.create(user)

    # Perform soft delete
    deleted = await repo.delete(created.id, hard_delete=False)
    assert deleted is True

    # Standard query should NOT return soft-deleted user
    assert await repo.get_by_id(created.id) is None
    assert await repo.exists(created.id) is False
    assert await repo.count() == 0

    # Query with include_deleted=True SHOULD return user
    deleted_user = await repo.get_by_id(created.id, include_deleted=True)
    assert deleted_user is not None
    assert deleted_user.is_deleted is True
    assert deleted_user.deleted_at is not None
    assert await repo.count(include_deleted=True) == 1


@pytest.mark.asyncio
async def test_user_repository_search_and_pagination(
    db_session: AsyncSession,
) -> None:
    repo = UserRepository(session=db_session)

    # Seed 5 users
    for i in range(5):
        await repo.create(
            User(
                email=f"user_{i}@company.com",
                hashed_password="hash",
                full_name=f"Employee {i}",
                is_active=(i % 2 == 0),
            )
        )

    # Search with keyword filter
    results, total = await repo.search_users(query="Employee 2")
    assert total == 1
    assert results[0].email == "user_2@company.com"

    # Filter active only
    active_users, active_count = await repo.search_users(is_active=True)
    assert active_count == 3
    assert len(active_users) == 3

    # Pagination test
    page_1, total_all = await repo.search_users(skip=0, limit=2)
    assert total_all == 5
    assert len(page_1) == 2


@pytest.mark.asyncio
async def test_role_repository_operations(db_session: AsyncSession) -> None:
    role_repo = RoleRepository(session=db_session)
    perm_repo = PermissionRepository(session=db_session)

    # 1. System roles
    sys_role = Role(
        name="admin",
        display_name="Administrator",
        is_system_role=True,
    )
    custom_role = Role(
        name="custom_viewer",
        display_name="Custom Viewer",
        is_system_role=False,
    )
    await role_repo.create(sys_role)
    await role_repo.create(custom_role)

    system_roles = await role_repo.get_system_roles()
    assert len(system_roles) == 1
    assert system_roles[0].name == "admin"

    # 2. Permission assignment and removal
    perm = Permission(code="admin:all", resource="admin", action="all")
    await perm_repo.create(perm)

    await role_repo.assign_permission(sys_role, perm)
    with_perms = await role_repo.get_with_permissions(sys_role.id)
    assert with_perms is not None
    assert len(with_perms.permissions) == 1

    await role_repo.remove_permission(sys_role, perm)
    assert len(sys_role.permissions) == 0


@pytest.mark.asyncio
async def test_permission_repository_queries(db_session: AsyncSession) -> None:
    repo = PermissionRepository(session=db_session)

    p1 = Permission(code="knowledge:read", resource="knowledge", action="read")
    p2 = Permission(code="knowledge:write", resource="knowledge", action="write")
    p3 = Permission(code="search:query", resource="search", action="query")
    await repo.bulk_create([p1, p2, p3])

    # Query by code
    found = await repo.get_by_code("knowledge:read")
    assert found is not None
    assert found.code == "knowledge:read"

    # Query by resource namespace
    knowledge_perms = await repo.get_by_resource("knowledge")
    assert len(knowledge_perms) == 2
    assert [p.code for p in knowledge_perms] == ["knowledge:read", "knowledge:write"]

    # Existence check
    assert await repo.permission_exists("search:query") is True
    assert await repo.permission_exists("nonexistent:code") is False
