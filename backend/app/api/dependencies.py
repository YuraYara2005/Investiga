"""Shared API Dependencies, Security Providers, and Authorization Guards for Investiga.

This module provides FastAPI dependency injectors (`Depends`) for configuration,
isolated database sessions, contextual loggers, service factories, and RBAC authorization
guards (`get_current_user`, `get_current_active_user`, `require_roles`, `require_permissions`).
"""

import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import TYPE_CHECKING, Annotated

import structlog
from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.repositories import UserRepository
from app.auth.services import AuthService, TokenService, UserService
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.security import TokenPayload, decode_token
from app.db.session import get_db_session

if TYPE_CHECKING:
    from app.knowledge import KnowledgeService
    from app.storage import StorageService
from app.exceptions.domain import (
    ForbiddenException,
    UnauthorizedException,
)

logger = get_logger(__name__)


# ------------------------------------------------------------------------------
# Core Infrastructure Dependencies
# ------------------------------------------------------------------------------


def get_current_settings() -> Settings:
    """FastAPI dependency to inject validated application configuration."""
    return get_settings()


async def get_database(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an isolated, transaction-managed AsyncSession."""
    yield session


def get_request_id(request: Request) -> str:
    """Extract or retrieve the active correlation request ID from request state."""
    return getattr(request.state, "request_id", None) or request.headers.get(
        "X-Request-ID", "unknown"
    )


def get_contextual_logger(
    request: Request,
) -> structlog.stdlib.BoundLogger:
    """Provide a structured logger bound with the current request context."""
    request_id = get_request_id(request)
    return logger.bind(request_id=request_id)


# ------------------------------------------------------------------------------
# Service Layer Dependency Factories
# ------------------------------------------------------------------------------


def get_token_service(
    settings: Settings = Depends(get_current_settings),
) -> TokenService:
    """FastAPI dependency providing an initialized TokenService instance."""
    return TokenService(settings=settings)


def get_auth_service(
    session: AsyncSession = Depends(get_database),
    token_service: TokenService = Depends(get_token_service),
    settings: Settings = Depends(get_current_settings),
) -> AuthService:
    """FastAPI dependency providing an initialized AuthService instance with active session."""
    return AuthService(
        session=session,
        token_service=token_service,
    )


def get_user_service(
    session: AsyncSession = Depends(get_database),
) -> UserService:
    """FastAPI dependency providing an initialized UserService instance with active session."""
    return UserService(session=session)


def get_storage_service(
    settings: Settings = Depends(get_current_settings),
) -> "StorageService":
    """FastAPI dependency providing an initialized StorageService instance."""
    from app.storage import StorageService

    return StorageService(settings=settings)


def get_knowledge_service(
    session: AsyncSession = Depends(get_database),
    storage_service: "StorageService" = Depends(get_storage_service),
) -> "KnowledgeService":
    """FastAPI dependency providing an initialized KnowledgeService instance."""
    from app.knowledge import KnowledgeService

    return KnowledgeService(
        session=session,
        storage_service=storage_service,
    )


# ------------------------------------------------------------------------------
# Cryptographic Token Extraction & User Identity Dependencies
# ------------------------------------------------------------------------------


async def get_current_token_payload(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    settings: Settings = Depends(get_current_settings),
) -> TokenPayload:
    """Extract and cryptographically validate the JWT bearer access token from Authorization header.

    Args:
        authorization: The raw Authorization header string ('Bearer <token>').
        settings: Application settings.

    Returns:
        TokenPayload: Decoded and validated JWT claims model.

    Raises:
        UnauthorizedException: If header is missing, malformed, or signature/claims are invalid.
    """
    if not authorization:
        raise UnauthorizedException(
            message="Authorization header is required.",
            details={"error_subcode": "MISSING_AUTHORIZATION_HEADER"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedException(
            message="Authorization scheme must be 'Bearer <token>'.",
            details={"error_subcode": "INVALID_AUTHORIZATION_SCHEME"},
        )

    return decode_token(
        token=token,
        expected_type="access",
        settings=settings,
    )


async def get_current_user(
    payload: TokenPayload = Depends(get_current_token_payload),
    session: AsyncSession = Depends(get_database),
) -> User:
    """Resolve the authenticated User entity from the database using validated JWT claims.

    Args:
        payload: Validated JWT access token payload.
        session: Active asynchronous database session.

    Returns:
        User: Fully hydrated User entity with eagerly loaded roles and permissions.

    Raises:
        UnauthorizedException: If user ID in token does not exist.
    """
    try:
        user_uuid = uuid.UUID(payload.sub)
    except ValueError as exc:
        raise UnauthorizedException(
            message="Invalid subject identifier format in token.",
            details={"error_subcode": "INVALID_TOKEN_SUBJECT"},
        ) from exc

    user_repo = UserRepository(session=session)
    user = await user_repo.get_with_roles_and_permissions(user_uuid)

    if user is None:
        raise UnauthorizedException(
            message="Authenticated user account no longer exists.",
            details={"error_subcode": "USER_NOT_FOUND"},
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the authenticated principal is active and not soft-deleted.

    Args:
        current_user: Authenticated User entity.

    Returns:
        User: Validated active User entity.

    Raises:
        ForbiddenException: If user account is disabled or soft-deleted.
    """
    if current_user.is_deleted or not current_user.is_active:
        raise ForbiddenException(
            message="User account is deactivated or suspended.",
            details={"user_id": str(current_user.id)},
        )
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Ensure the authenticated principal possesses global superuser administrative privileges.

    Args:
        current_user: Active User entity.

    Returns:
        User: Superuser User entity.

    Raises:
        ForbiddenException: If user lacks superuser status.
    """
    if not current_user.is_superuser:
        raise ForbiddenException(
            message="Superuser privileges required for this operation.",
            details={"error_subcode": "SUPERUSER_REQUIRED"},
        )
    return current_user


# ------------------------------------------------------------------------------
# RBAC Authorization Gates (Role & Permission Requirement Factories)
# ------------------------------------------------------------------------------


def require_roles(*required_roles: str) -> Callable[..., Awaitable[User]]:
    """Dependency factory enforcing that the authenticated user holds at least one of the specified roles.

    Superusers automatically bypass role checks.

    Args:
        *required_roles: One or more role names permitted to access the endpoint.

    Returns:
        Callable: FastAPI dependency returning the authorized active User.

    Example:
        @router.get("/admin/metrics", dependencies=[Depends(require_roles("admin", "incident_commander"))])
    """

    async def role_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.is_superuser:
            return current_user

        user_roles = set(current_user.role_names)
        if not any(role in user_roles for role in required_roles):
            logger.warning(
                "rbac_role_check_failed",
                user_id=str(current_user.id),
                required_roles=list(required_roles),
                user_roles=list(user_roles),
            )
            raise ForbiddenException(
                message="Insufficient role privileges to perform this action.",
                details={
                    "required_roles": list(required_roles),
                    "user_roles": list(user_roles),
                },
            )
        return current_user

    return role_checker


def require_permissions(*required_permissions: str) -> Callable[..., Awaitable[User]]:
    """Dependency factory enforcing that the authenticated user holds ALL specified permissions.

    Superusers automatically bypass permission checks.

    Args:
        *required_permissions: Granular permission codes required (e.g. 'investigations:create').

    Returns:
        Callable: FastAPI dependency returning the authorized active User.

    Example:
        @router.post("/investigations", dependencies=[Depends(require_permissions("investigations:create"))])
    """

    async def permission_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.is_superuser:
            return current_user

        user_perms = current_user.permission_codes
        missing_permissions = [
            perm for perm in required_permissions if perm not in user_perms
        ]

        if missing_permissions:
            logger.warning(
                "rbac_permission_check_failed",
                user_id=str(current_user.id),
                missing_permissions=missing_permissions,
            )
            raise ForbiddenException(
                message="Insufficient operational permissions to perform this action.",
                details={"missing_permissions": missing_permissions},
            )
        return current_user

    return permission_checker
