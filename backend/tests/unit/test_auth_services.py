"""Unit tests for Identity Service Layer and Business Logic."""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.auth.models import Permission, Role
from app.auth.repositories import (
    PermissionRepository,
    RoleRepository,
    UserRepository,
)
from app.auth.schemas import (
    ChangePasswordRequest,
    RefreshTokenRequest,
    UpdateProfileRequest,
    UserLoginRequest,
    UserRegisterRequest,
)
from app.auth.services import (
    AuthService,
    PasswordPolicy,
    UserService,
)
from app.db.base import Base
from app.exceptions.domain import (
    ConflictException,
    ForbiddenException,
    UnauthorizedException,
    ValidationException,
)


@pytest_asyncio.fixture
async def async_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an isolated in-memory SQLite async engine for service testing."""
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


def test_password_policy_validation() -> None:
    policy = PasswordPolicy(min_length=8)

    # Valid password
    policy.validate("Valid#Pass123")

    # Too short
    with pytest.raises(ValidationException) as exc_info:
        policy.validate("Sh1#")
    assert "policy_violations" in exc_info.value.details

    # Missing uppercase
    with pytest.raises(ValidationException):
        policy.validate("nouppercase123#")

    # Missing lowercase
    with pytest.raises(ValidationException):
        policy.validate("NOLOWERCASE123#")

    # Missing digit
    with pytest.raises(ValidationException):
        policy.validate("NoDigitsHere#!")

    # Missing special character
    with pytest.raises(ValidationException):
        policy.validate("NoSpecialChars123")


@pytest.mark.asyncio
async def test_auth_service_register_success(db_session: AsyncSession) -> None:
    role_repo = RoleRepository(session=db_session)
    await role_repo.create(Role(name="analyst", display_name="Incident Analyst"))

    auth_service = AuthService(session=db_session)

    register_req = UserRegisterRequest(
        email="analyst.alice@investiga.internal",
        password="Secure#Password2026",
        full_name="Alice Smith",
    )

    response = await auth_service.register(register_req)
    assert response.email == "analyst.alice@investiga.internal"
    assert response.full_name == "Alice Smith"
    assert response.is_active is True
    assert "analyst" in response.roles


@pytest.mark.asyncio
async def test_auth_service_register_duplicate_email(db_session: AsyncSession) -> None:
    auth_service = AuthService(session=db_session)

    register_req = UserRegisterRequest(
        email="duplicate@investiga.internal",
        password="Secure#Password2026",
        full_name="Duplicate User",
    )

    await auth_service.register(register_req)

    with pytest.raises(ConflictException) as exc_info:
        await auth_service.register(register_req)
    assert "already exists" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_auth_service_authenticate_success(db_session: AsyncSession) -> None:
    role_repo = RoleRepository(session=db_session)
    perm_repo = PermissionRepository(session=db_session)

    perm = await perm_repo.create(
        Permission(code="investigations:read", resource="investigations", action="read")
    )
    role = Role(name="analyst", display_name="Incident Analyst")
    role.permissions = [perm]
    await role_repo.create(role)

    auth_service = AuthService(session=db_session)

    # 1. Register
    await auth_service.register(
        UserRegisterRequest(
            email="bob@investiga.internal",
            password="Secure#Password2026",
            full_name="Bob Jones",
        )
    )

    # 2. Authenticate
    login_req = UserLoginRequest(
        email="bob@investiga.internal",
        password="Secure#Password2026",
    )
    token_response = await auth_service.authenticate(login_req)

    assert token_response.access_token is not None
    assert token_response.refresh_token is not None
    assert token_response.token_type.lower() == "bearer"
    assert token_response.expires_in > 0


@pytest.mark.asyncio
async def test_auth_service_authenticate_invalid_credentials(
    db_session: AsyncSession,
) -> None:
    auth_service = AuthService(session=db_session)

    await auth_service.register(
        UserRegisterRequest(
            email="charlie@investiga.internal",
            password="Secure#Password2026",
            full_name="Charlie Brown",
        )
    )

    # 1. Invalid Password
    with pytest.raises(UnauthorizedException) as exc_info:
        await auth_service.authenticate(
            UserLoginRequest(
                email="charlie@investiga.internal",
                password="Wrong#Password999",
            )
        )
    assert "Invalid email or password" in exc_info.value.message

    # 2. Nonexistent Email (Timing attack safe dummy hash test)
    with pytest.raises(UnauthorizedException) as exc_info:
        await auth_service.authenticate(
            UserLoginRequest(
                email="nonexistent@investiga.internal",
                password="Secure#Password2026",
            )
        )
    assert "Invalid email or password" in exc_info.value.message


@pytest.mark.asyncio
async def test_auth_service_authenticate_inactive_user(
    db_session: AsyncSession,
) -> None:
    auth_service = AuthService(session=db_session)
    user_repo = UserRepository(session=db_session)

    user_res = await auth_service.register(
        UserRegisterRequest(
            email="inactive@investiga.internal",
            password="Secure#Password2026",
            full_name="Inactive User",
        )
    )

    # Deactivate account
    user = await user_repo.get_by_id(user_res.id)
    assert user is not None
    user.is_active = False
    await user_repo.update(user)
    await db_session.commit()

    with pytest.raises(ForbiddenException):
        await auth_service.authenticate(
            UserLoginRequest(
                email="inactive@investiga.internal",
                password="Secure#Password2026",
            )
        )


@pytest.mark.asyncio
async def test_auth_service_refresh_token_flow(db_session: AsyncSession) -> None:
    auth_service = AuthService(session=db_session)

    await auth_service.register(
        UserRegisterRequest(
            email="refresh@investiga.internal",
            password="Secure#Password2026",
            full_name="Refresh User",
        )
    )

    token_res = await auth_service.authenticate(
        UserLoginRequest(
            email="refresh@investiga.internal",
            password="Secure#Password2026",
        )
    )

    # Refresh tokens
    refreshed = await auth_service.refresh_access_token(
        RefreshTokenRequest(refresh_token=token_res.refresh_token)
    )
    assert refreshed.access_token is not None
    assert refreshed.refresh_token is not None


@pytest.mark.asyncio
async def test_user_service_profile_and_password_lifecycle(
    db_session: AsyncSession,
) -> None:
    auth_service = AuthService(session=db_session)
    user_service = UserService(session=db_session)

    # 1. Register User
    registered = await auth_service.register(
        UserRegisterRequest(
            email="lifecycle@investiga.internal",
            password="Old#Password2026",
            full_name="Initial Name",
        )
    )

    # 2. Get Profile
    profile = await user_service.get_current_user_profile(registered.id)
    assert profile.email == "lifecycle@investiga.internal"
    assert profile.full_name == "Initial Name"

    # 3. Update Profile
    updated_profile = await user_service.update_profile(
        registered.id, UpdateProfileRequest(full_name="Updated Name")
    )
    assert updated_profile.full_name == "Updated Name"

    # 4. Change Password - Invalid Current
    with pytest.raises(UnauthorizedException):
        await user_service.change_password(
            registered.id,
            ChangePasswordRequest(
                current_password="WrongCurrentPassword#1",
                new_password="New#Password2026",
            ),
        )

    # 5. Change Password - Success
    await user_service.change_password(
        registered.id,
        ChangePasswordRequest(
            current_password="Old#Password2026",
            new_password="New#Password2026",
        ),
    )

    # 6. Authenticate with new password
    token_res = await auth_service.authenticate(
        UserLoginRequest(
            email="lifecycle@investiga.internal",
            password="New#Password2026",
        )
    )
    assert token_res.access_token is not None
