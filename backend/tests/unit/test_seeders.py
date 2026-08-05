"""Unit and Integration Tests for Database Seeders and RBAC Matrix Provisioning.

Tests seeder idempotency, role-permission matrix integrity, administrator account
creation, and production safety guards.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.auth.models import Permission, Role, User
from app.core.config import Settings
from app.core.security import verify_password
from app.db.base import Base
from app.db.seeders import (
    DEFAULT_ROLES,
    SYSTEM_PERMISSIONS,
    seed_admin,
    seed_all,
    seed_permissions,
    seed_roles,
)


@pytest_asyncio.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create isolated SQLite async engine with schema."""
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
    """Create session factory bound to test engine."""
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.mark.asyncio
async def test_seed_permissions_idempotency(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Test seed_permissions creates all entitlements and is strictly idempotent."""
    async with session_factory() as session:
        # First execution
        perms_1 = await seed_permissions(session)
        await session.commit()
        assert len(perms_1) == len(SYSTEM_PERMISSIONS)

        # Count in DB
        count_stmt = select(func.count()).select_from(Permission)
        count_1 = (await session.execute(count_stmt)).scalar_one()
        assert count_1 == len(SYSTEM_PERMISSIONS)

        # Second execution (idempotency check)
        perms_2 = await seed_permissions(session)
        await session.commit()
        assert len(perms_2) == len(SYSTEM_PERMISSIONS)

        count_2 = (await session.execute(count_stmt)).scalar_one()
        assert count_2 == len(SYSTEM_PERMISSIONS)


@pytest.mark.asyncio
async def test_seed_roles_matrix_and_idempotency(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Test seed_roles creates all roles with appropriate permission matrices and is idempotent."""
    async with session_factory() as session:
        # 1. Seed roles
        roles_map = await seed_roles(session)
        await session.commit()

        assert len(roles_map) == len(DEFAULT_ROLES)
        assert "super_admin" in roles_map
        assert "admin" in roles_map
        assert "ai_engineer" in roles_map
        assert "investigator" in roles_map
        assert "analyst" in roles_map
        assert "viewer" in roles_map

        # Verify Super Admin has all permissions
        super_admin = roles_map["super_admin"]
        assert len(super_admin.permissions) == len(SYSTEM_PERMISSIONS)

        # Verify Admin has operational perms but not system:admin
        admin = roles_map["admin"]
        admin_perm_codes = {p.code for p in admin.permissions}
        assert "users:create" in admin_perm_codes
        assert "investigations:create" in admin_perm_codes
        assert "system:admin" not in admin_perm_codes

        # Verify Viewer has read-only perms
        viewer = roles_map["viewer"]
        viewer_perm_codes = {p.code for p in viewer.permissions}
        assert viewer_perm_codes == {
            "knowledge:view",
            "investigations:view",
            "search:query",
        }

        # 2. Re-run seeding (idempotency verification)
        roles_map_2 = await seed_roles(session)
        await session.commit()
        assert len(roles_map_2) == len(DEFAULT_ROLES)

        count_stmt = select(func.count()).select_from(Role)
        role_count = (await session.execute(count_stmt)).scalar_one()
        assert role_count == len(DEFAULT_ROLES)


@pytest.mark.asyncio
async def test_seed_admin_idempotency_and_security(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Test seed_admin provisions Super Admin account with Argon2 hash and runs idempotently."""
    custom_creds = {
        "email": "root.admin@investiga.internal",
        "password": "SuperSecureAdminPassword#2026!",
        "full_name": "Root Administrator",
    }

    async with session_factory() as session:
        # First execution
        admin_1 = await seed_admin(
            session=session,
            custom_credentials=custom_creds,
        )
        await session.commit()

        assert admin_1.email == "root.admin@investiga.internal"
        assert admin_1.is_superuser is True
        assert admin_1.is_active is True
        assert admin_1.is_verified is True
        assert "super_admin" in admin_1.role_names
        assert verify_password(custom_creds["password"], admin_1.hashed_password)

        # Second execution (idempotency check)
        admin_2 = await seed_admin(
            session=session,
            custom_credentials=custom_creds,
        )
        await session.commit()

        assert admin_2.id == admin_1.id
        assert admin_2.email == admin_1.email

        # Verify exactly one user in DB
        count_stmt = select(func.count()).select_from(User)
        user_count = (await session.execute(count_stmt)).scalar_one()
        assert user_count == 1


@pytest.mark.asyncio
async def test_seed_all_master_orchestration(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Test seed_all orchestrates complete initialization in a single transaction."""
    async with session_factory() as session:
        summary = await seed_all(session=session, allow_production=False)
        assert summary["status"] == "success"
        assert summary["permissions_count"] == len(SYSTEM_PERMISSIONS)
        assert summary["roles_count"] == len(DEFAULT_ROLES)
        assert "@" in summary["admin_email"]
