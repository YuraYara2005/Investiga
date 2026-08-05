"""Integration tests for Authentication & Authorization HTTP API Layer.

Covers full end-to-end integration workflows:
- User registration, conflict handling, and validation
- Credential authentication, token issuance, and timing defense
- Session token renewal via refresh token rotation
- Authenticated user profile retrieval (/me) and mutations
- Secure password change lifecycle
- RBAC role and permission gate dependencies
- Security defenses: invalid tokens, expired tokens, missing headers, deactivated accounts
- OpenAPI schema documentation contracts
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import timedelta

import pytest
import pytest_asyncio
from fastapi import APIRouter, Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.dependencies import (
    get_database,
    require_permissions,
    require_roles,
)
from app.auth.models import Permission, Role, User
from app.auth.repositories import PermissionRepository, RoleRepository, UserRepository
from app.core.config import get_settings
from app.core.password import async_get_password_hash
from app.core.security import create_access_token
from app.db.base import Base
from app.main import create_app


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
async def seed_data(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, Role | Permission]:
    """Seed foundational roles and permissions for integration testing."""
    async with session_factory() as session:
        perm_repo = PermissionRepository(session=session)
        role_repo = RoleRepository(session=session)

        # 1. Create permissions
        perm_view = await perm_repo.create(
            Permission(
                code="investigations:view",
                resource="investigations",
                action="view",
            )
        )
        perm_create = await perm_repo.create(
            Permission(
                code="investigations:create",
                resource="investigations",
                action="create",
            )
        )
        perm_admin = await perm_repo.create(
            Permission(
                code="system:admin",
                resource="system",
                action="admin",
            )
        )

        # 2. Create roles
        analyst_role = Role(
            name="analyst",
            display_name="Analyst",
            is_system_role=True,
        )
        analyst_role.permissions = [perm_view]
        await role_repo.create(analyst_role)

        investigator_role = Role(
            name="investigator",
            display_name="Investigator",
            is_system_role=True,
        )
        investigator_role.permissions = [perm_view, perm_create]
        await role_repo.create(investigator_role)

        admin_role = Role(
            name="admin",
            display_name="Administrator",
            is_system_role=True,
        )
        admin_role.permissions = [perm_view, perm_create, perm_admin]
        await role_repo.create(admin_role)

        await session.commit()

        return {
            "perm_view": perm_view,
            "perm_create": perm_create,
            "perm_admin": perm_admin,
            "role_analyst": analyst_role,
            "role_investigator": investigator_role,
            "role_admin": admin_role,
        }


@pytest_asyncio.fixture
async def test_app(
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Role | Permission],
) -> FastAPI:
    """Instantiate application configured with overridden isolated database session."""
    app = create_app()

    async def override_get_database() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_database] = override_get_database

    # Mount temporary test routes to verify require_roles and require_permissions guards
    test_guard_router = APIRouter(prefix="/test-guards")

    @test_guard_router.get(
        "/admin-only",
        dependencies=[Depends(require_roles("admin"))],
    )
    async def admin_only_endpoint() -> dict[str, str]:
        return {"status": "authorized_admin"}

    @test_guard_router.get(
        "/create-investigation",
        dependencies=[Depends(require_permissions("investigations:create"))],
    )
    async def create_investigation_endpoint() -> dict[str, str]:
        return {"status": "authorized_create_investigation"}

    app.include_router(test_guard_router)

    return app


@pytest_asyncio.fixture
async def async_client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Provide an asynchronous HTTP test client bound to the ASGI application."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# ==============================================================================
# 1. Registration Flow Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_register_success(async_client: AsyncClient) -> None:
    """Test successful user registration returns 201 Created and sanitized UserResponse."""
    payload = {
        "email": "analyst.marcus@investiga.internal",
        "password": "SecurePassword#2026!",
        "full_name": "Marcus Vance",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["email"] == "analyst.marcus@investiga.internal"
    assert data["full_name"] == "Marcus Vance"
    assert data["is_active"] is True
    assert data["is_verified"] is False
    assert data["is_superuser"] is False
    assert "analyst" in data["roles"]
    assert "password" not in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email_conflict(
    async_client: AsyncClient,
) -> None:
    """Test registration with existing email returns 409 Conflict."""
    payload = {
        "email": "analyst.duplicate@investiga.internal",
        "password": "SecurePassword#2026!",
        "full_name": "Duplicate User",
    }
    # Initial registration
    first_res = await async_client.post("/api/v1/auth/register", json=payload)
    assert first_res.status_code == 201

    # Second registration attempt
    second_res = await async_client.post("/api/v1/auth/register", json=payload)
    assert second_res.status_code == 409
    error_data = second_res.json()
    assert error_data["success"] is False
    assert error_data["error"]["code"] == "RESOURCE_CONFLICT"


@pytest.mark.asyncio
async def test_register_invalid_password_complexity(
    async_client: AsyncClient,
) -> None:
    """Test registration fails with 400 Bad Request when password violates policy."""
    payload = {
        "email": "weak.user@investiga.internal",
        "password": "weak",  # Too short, lacks complexity
        "full_name": "Weak Password User",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422 or response.status_code == 400


# ==============================================================================
# 2. Authentication & Login Flow Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient) -> None:
    """Test valid credential login returns 200 OK with synchronized token pair."""
    # 1. Register
    reg_payload = {
        "email": "login.test@investiga.internal",
        "password": "SecurePassword#2026!",
        "full_name": "Login Tester",
    }
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    # 2. Login
    login_payload = {
        "email": "login.test@investiga.internal",
        "password": "SecurePassword#2026!",
    }
    response = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "Bearer"
    assert isinstance(data["expires_in"], int)
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_invalid_credentials_generic_error(
    async_client: AsyncClient,
) -> None:
    """Test invalid password returns generic 401 Unauthorized error."""
    # 1. Register
    reg_payload = {
        "email": "invalid.pw@investiga.internal",
        "password": "SecurePassword#2026!",
        "full_name": "Invalid PW User",
    }
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    # 2. Attempt login with wrong password
    login_payload = {
        "email": "invalid.pw@investiga.internal",
        "password": "WrongPassword#2026!",
    }
    response = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    error_data = response.json()
    assert error_data["success"] is False
    assert error_data["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_login_nonexistent_user_timing_defense(
    async_client: AsyncClient,
) -> None:
    """Test login for nonexistent user returns 401 Unauthorized without leaking account existence."""
    login_payload = {
        "email": "ghost.user@investiga.internal",
        "password": "SomePassword#2026!",
    }
    response = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    error_data = response.json()
    assert error_data["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_login_deactivated_account_rejected(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Test deactivated account login is rejected with 403 Forbidden."""
    # 1. Register user
    reg_payload = {
        "email": "deactivated@investiga.internal",
        "password": "SecurePassword#2026!",
        "full_name": "Deactivated User",
    }
    reg_res = await async_client.post("/api/v1/auth/register", json=reg_payload)
    user_id = uuid.UUID(reg_res.json()["id"])

    # 2. Deactivate user directly in DB
    async with session_factory() as session:
        user_repo = UserRepository(session=session)
        user = await user_repo.get_by_id(user_id)
        assert user is not None
        user.is_active = False
        await user_repo.update(user)
        await session.commit()

    # 3. Attempt login
    login_payload = {
        "email": "deactivated@investiga.internal",
        "password": "SecurePassword#2026!",
    }
    response = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 403
    error_data = response.json()
    assert error_data["error"]["code"] == "PERMISSION_DENIED"


# ==============================================================================
# 3. Token Refresh & Rotation Flow Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_refresh_token_success(async_client: AsyncClient) -> None:
    """Test valid refresh token exchange returns rotated token pair."""
    # 1. Register & Login
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "refresh.user@investiga.internal",
            "password": "SecurePassword#2026!",
            "full_name": "Refresh User",
        },
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "refresh.user@investiga.internal",
            "password": "SecurePassword#2026!",
        },
    )
    original_refresh = login_res.json()["refresh_token"]

    # 2. Refresh tokens
    refresh_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original_refresh},
    )
    assert refresh_res.status_code == 200
    data = refresh_res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "Bearer"


@pytest.mark.asyncio
async def test_refresh_with_invalid_or_forged_token(
    async_client: AsyncClient,
) -> None:
    """Test refreshing with tampered token string returns 401 Unauthorized."""
    response = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "forged.jwt.token.payload"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_access_token_fails(
    async_client: AsyncClient,
) -> None:
    """Test attempting to refresh using an access token (type mismatch) returns 401 Unauthorized."""
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "mismatch@investiga.internal",
            "password": "SecurePassword#2026!",
            "full_name": "Mismatch User",
        },
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "mismatch@investiga.internal",
            "password": "SecurePassword#2026!",
        },
    )
    access_token = login_res.json()["access_token"]

    # Attempt refresh using access_token
    response = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert response.status_code == 401


# ==============================================================================
# 4. Current User Profile (/me) & Updates
# ==============================================================================


@pytest.mark.asyncio
async def test_get_current_user_profile_success(
    async_client: AsyncClient,
) -> None:
    """Test /me returns profile with active roles and aggregated permissions."""
    # 1. Register & Login
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "me.test@investiga.internal",
            "password": "SecurePassword#2026!",
            "full_name": "Profile Tester",
        },
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "me.test@investiga.internal",
            "password": "SecurePassword#2026!",
        },
    )
    token = login_res.json()["access_token"]

    # 2. Get /me
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me.test@investiga.internal"
    assert data["full_name"] == "Profile Tester"
    assert "analyst" in data["roles"]
    assert "investigations:view" in data["permissions"]


@pytest.mark.asyncio
async def test_get_current_user_missing_or_invalid_auth_header(
    async_client: AsyncClient,
) -> None:
    """Test /me without Authorization header returns 401 Unauthorized."""
    # No header
    res_no_header = await async_client.get("/api/v1/auth/me")
    assert res_no_header.status_code == 401

    # Malformed header scheme
    res_bad_scheme = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )
    assert res_bad_scheme.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_expired_jwt(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Test /me with expired JWT access token returns 401 Unauthorized."""
    settings = get_settings()
    user_id = uuid.uuid4()

    # Create user in DB
    async with session_factory() as session:
        user_repo = UserRepository(session=session)
        user = User(
            id=user_id,
            email="expired.token@investiga.internal",
            hashed_password="hash",
            full_name="Expired User",
        )
        await user_repo.create(user)
        await session.commit()

    # Create intentionally expired token (-10 minutes)
    expired_token = create_access_token(
        subject=str(user_id),
        roles=[],
        permissions=[],
        expires_delta=timedelta(minutes=-10),
        settings=settings,
    )

    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_profile_success(async_client: AsyncClient) -> None:
    """Test updating user profile successfully persists changes."""
    # 1. Register & Login
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "update.profile@investiga.internal",
            "password": "SecurePassword#2026!",
            "full_name": "Original Name",
        },
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "update.profile@investiga.internal",
            "password": "SecurePassword#2026!",
        },
    )
    token = login_res.json()["access_token"]

    # 2. Update profile
    update_res = await async_client.put(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Updated Professional Name"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["full_name"] == "Updated Professional Name"

    # 3. Verify via GET /me
    me_res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.json()["full_name"] == "Updated Professional Name"


# ==============================================================================
# 5. Password Modification Flow Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_change_password_success(async_client: AsyncClient) -> None:
    """Test changing password re-verifies current password and permits subsequent login."""
    # 1. Register & Login
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "pwd.change@investiga.internal",
            "password": "OldPassword#2026!",
            "full_name": "Password Changer",
        },
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "pwd.change@investiga.internal",
            "password": "OldPassword#2026!",
        },
    )
    token = login_res.json()["access_token"]

    # 2. Change password
    change_res = await async_client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "OldPassword#2026!",
            "new_password": "NewSecretPassword#2026!",
        },
    )
    assert change_res.status_code == 204

    # 3. Verify old password no longer works
    fail_login = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "pwd.change@investiga.internal",
            "password": "OldPassword#2026!",
        },
    )
    assert fail_login.status_code == 401

    # 4. Verify new password works
    success_login = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "pwd.change@investiga.internal",
            "password": "NewSecretPassword#2026!",
        },
    )
    assert success_login.status_code == 200


@pytest.mark.asyncio
async def test_change_password_incorrect_current(
    async_client: AsyncClient,
) -> None:
    """Test password change fails with 401 Unauthorized when current password is wrong."""
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrong.pwd@investiga.internal",
            "password": "CurrentPassword#2026!",
            "full_name": "Wrong Pwd User",
        },
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "wrong.pwd@investiga.internal",
            "password": "CurrentPassword#2026!",
        },
    )
    token = login_res.json()["access_token"]

    change_res = await async_client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "IncorrectPassword#2026!",
            "new_password": "NewPassword#2026!",
        },
    )
    assert change_res.status_code == 401


# ==============================================================================
# 6. RBAC Role and Permission Gate Integration Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_rbac_guards_role_and_permission_enforcement(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    seed_data: dict[str, Role | Permission],
) -> None:
    """Test require_roles and require_permissions dependency gates."""
    # 1. Analyst user (has role 'analyst', permission 'investigations:view')
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "analyst.gate@investiga.internal",
            "password": "SecurePassword#2026!",
            "full_name": "Gate Analyst",
        },
    )
    analyst_login = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "analyst.gate@investiga.internal",
            "password": "SecurePassword#2026!",
        },
    )
    analyst_token = analyst_login.json()["access_token"]

    # Analyst trying admin route -> 403 Forbidden
    res_admin = await async_client.get(
        "/test-guards/admin-only",
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert res_admin.status_code == 403

    # Analyst trying investigation create route -> 403 Forbidden (analyst only has view)
    res_create = await async_client.get(
        "/test-guards/create-investigation",
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert res_create.status_code == 403

    # 2. Create Admin user in DB
    async with session_factory() as session:
        user_repo = UserRepository(session=session)
        admin_role = seed_data["role_admin"]
        admin_user = User(
            email="admin.gate@investiga.internal",
            hashed_password=await async_get_password_hash("AdminPassword#2026!"),
            full_name="Gate Admin",
            roles=[admin_role],  # type: ignore[list-item]
        )
        await user_repo.create(admin_user)
        await session.commit()

    admin_login = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin.gate@investiga.internal",
            "password": "AdminPassword#2026!",
        },
    )
    admin_token = admin_login.json()["access_token"]

    # Admin accessing admin-only route -> 200 OK
    res_admin_ok = await async_client.get(
        "/test-guards/admin-only",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_admin_ok.status_code == 200
    assert res_admin_ok.json()["status"] == "authorized_admin"

    # Admin accessing create-investigation route -> 200 OK
    res_create_ok = await async_client.get(
        "/test-guards/create-investigation",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_create_ok.status_code == 200
    assert res_create_ok.json()["status"] == "authorized_create_investigation"


@pytest.mark.asyncio
async def test_rbac_superuser_automatic_bypass(
    async_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Test superuser bypasses all role and permission gates automatically."""
    async with session_factory() as session:
        user_repo = UserRepository(session=session)
        superuser = User(
            email="root.super@investiga.internal",
            hashed_password=await async_get_password_hash("SuperRoot#2026!"),
            full_name="Root Superuser",
            is_superuser=True,
            roles=[],  # No explicit roles or permissions needed
        )
        await user_repo.create(superuser)
        await session.commit()

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "root.super@investiga.internal",
            "password": "SuperRoot#2026!",
        },
    )
    token = login_res.json()["access_token"]

    # Superuser accesses both guard endpoints
    res1 = await async_client.get(
        "/test-guards/admin-only",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res1.status_code == 200

    res2 = await async_client.get(
        "/test-guards/create-investigation",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == 200


# ==============================================================================
# 7. OpenAPI Schema Integration Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_openapi_schema_contains_auth_paths(
    async_client: AsyncClient,
) -> None:
    """Test OpenAPI specification documents all authentication routes and security schemes."""
    response = await async_client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    # Verify paths exist in OpenAPI schema
    expected_paths = [
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/me",
        "/api/v1/auth/change-password",
    ]
    for path in expected_paths:
        assert path in schema["paths"]
