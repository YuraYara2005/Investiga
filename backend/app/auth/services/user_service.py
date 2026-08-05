"""User Management Service for Investiga.

This module encapsulates user lifecycle management, profile mutations,
credential rotation, and administrative status management.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.repositories import UserRepository
from app.auth.repositories.interfaces import IUserRepository
from app.auth.schemas.requests import ChangePasswordRequest, UpdateProfileRequest
from app.auth.schemas.responses import CurrentUserResponse, UserResponse
from app.auth.services.validators import IdentityValidators
from app.core.password import async_get_password_hash, async_verify_password
from app.exceptions.domain import NotFoundException, UnauthorizedException


class UserService:
    """Service orchestrating user profile retrieval, credential updates, and account status."""

    def __init__(
        self,
        session: AsyncSession,
        user_repo: IUserRepository | None = None,
    ) -> None:
        self._session = session
        self._user_repo = user_repo or UserRepository(session=session)

    async def get_current_user_profile(self, user_id: uuid.UUID) -> CurrentUserResponse:
        """Retrieve the authenticated principal's profile, roles, and aggregated permissions.

        Args:
            user_id: User UUID.

        Returns:
            CurrentUserResponse: Populated user profile with active authorization claims.

        Raises:
            NotFoundException: If user record does not exist.
            ForbiddenException: If account is inactive or soft-deleted.
        """
        user = await self._user_repo.get_with_roles_and_permissions(user_id)
        if user is None:
            raise NotFoundException(
                message="User account not found.",
                details={"user_id": str(user_id)},
            )

        active_user = IdentityValidators.ensure_user_is_active(user)

        return CurrentUserResponse(
            id=active_user.id,
            email=active_user.email,
            full_name=active_user.full_name,
            is_active=active_user.is_active,
            is_verified=active_user.is_verified,
            is_superuser=active_user.is_superuser,
            roles=active_user.role_names,
            permissions=sorted(active_user.permission_codes),
            created_at=active_user.created_at,
            last_login_at=active_user.last_login_at,
        )

    async def update_profile(
        self, user_id: uuid.UUID, request: UpdateProfileRequest
    ) -> UserResponse:
        """Update mutable profile fields for a user account.

        Args:
            user_id: User UUID.
            request: Profile update payload.

        Returns:
            UserResponse: Updated user entity.
        """
        user = await self._user_repo.get_with_roles(user_id)
        if user is None:
            raise NotFoundException(
                message="User account not found.",
                details={"user_id": str(user_id)},
            )

        active_user = IdentityValidators.ensure_user_is_active(user)

        if request.full_name is not None:
            active_user.full_name = request.full_name

        await self._user_repo.update(active_user)
        await self._session.commit()

        return UserResponse(
            id=active_user.id,
            email=active_user.email,
            full_name=active_user.full_name,
            is_active=active_user.is_active,
            is_verified=active_user.is_verified,
            is_superuser=active_user.is_superuser,
            roles=active_user.role_names,
            created_at=active_user.created_at,
            last_login_at=active_user.last_login_at,
        )

    async def change_password(
        self, user_id: uuid.UUID, request: ChangePasswordRequest
    ) -> None:
        """Change a user's password after validating current credentials and policy rules.

        Args:
            user_id: User UUID.
            request: Payload containing current and new plaintext passwords.

        Raises:
            UnauthorizedException: If current password verification fails.
            ValidationException: If new password fails complexity policy.
        """
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundException(
                message="User account not found.",
                details={"user_id": str(user_id)},
            )

        active_user = IdentityValidators.ensure_user_is_active(user)

        # 1. Verify current password
        is_current_valid = await async_verify_password(
            plain_password=request.current_password,
            hashed_password=active_user.hashed_password,
        )
        if not is_current_valid:
            raise UnauthorizedException(
                message="Current password is incorrect.",
                details={"error_subcode": "INVALID_CURRENT_PASSWORD"},
            )

        # 2. Validate new password against complexity policy
        IdentityValidators.validate_password_complexity(request.new_password)

        # 3. Hash new password and persist
        new_hash = await async_get_password_hash(request.new_password)
        active_user.hashed_password = new_hash

        await self._user_repo.update(active_user)
        await self._session.commit()

    async def deactivate_user(self, user_id: uuid.UUID) -> None:
        """Administratively deactivate a user account.

        Args:
            user_id: User UUID.
        """
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundException(
                message="User account not found.",
                details={"user_id": str(user_id)},
            )

        user.is_active = False
        await self._user_repo.update(user)
        await self._session.commit()
