"""Authentication and Registration Orchestration Service for Investiga.

This module encapsulates core authentication workflows: user registration,
Argon2id credential verification (with timing-attack defense), token pair issuance,
and session renewal via refresh token rotation.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.repositories import RoleRepository, UserRepository
from app.auth.repositories.interfaces import IRoleRepository, IUserRepository
from app.auth.schemas.requests import (
    RefreshTokenRequest,
    UserLoginRequest,
    UserRegisterRequest,
)
from app.auth.schemas.responses import TokenResponse, UserResponse
from app.auth.services.password_policy import PasswordPolicy, default_password_policy
from app.auth.services.token_service import TokenService
from app.auth.services.validators import IdentityValidators
from app.core.logging import get_logger
from app.core.password import async_get_password_hash, async_verify_password
from app.exceptions.domain import ForbiddenException, UnauthorizedException

logger = get_logger(__name__)


class AuthService:
    """Service coordinating user registration, credential authentication, and token issuance."""

    # Precomputed valid Argon2id hash used to mitigate user enumeration timing attacks
    DUMMY_ARGON2_HASH = (
        "$argon2id$v=19$m=65536,t=3,p=4$ytkbA0AIwTgHAOC8dw5B6A$Tg5zhy7lskyKvKG4Mh7x7cwZGjzdOoAZc+jgFg/nwBs"
    )

    def __init__(
        self,
        session: AsyncSession,
        user_repo: IUserRepository | None = None,
        role_repo: IRoleRepository | None = None,
        token_service: TokenService | None = None,
        password_policy: PasswordPolicy = default_password_policy,
    ) -> None:
        self._session = session
        self._user_repo = user_repo or UserRepository(session=session)
        self._role_repo = role_repo or RoleRepository(session=session)
        self._token_service = token_service or TokenService()
        self._password_policy = password_policy

    async def register(
        self,
        request: UserRegisterRequest,
        default_role_name: str = "analyst",
    ) -> UserResponse:
        """Register a new user account with validated credentials and initial role assignment.

        Args:
            request: Registration payload containing email, plaintext password, and full name.
            default_role_name: Initial role assigned to the new user.

        Returns:
            UserResponse: Sanitized representation of the created user record.

        Raises:
            ValidationException: If password violates corporate complexity rules.
            ConflictException: If the email address is already registered.
        """
        # 1. Validate password against complexity rules
        IdentityValidators.validate_password_complexity(
            password=request.password, policy=self._password_policy
        )

        # 2. Assert email uniqueness
        normalized_email = request.email.strip().lower()
        await IdentityValidators.ensure_email_is_available(
            user_repo=self._user_repo, email=normalized_email
        )

        # 3. Hash password asynchronously via Argon2id
        hashed_password = await async_get_password_hash(request.password)

        # 4. Resolve default system role
        initial_roles: list[Role] = []
        default_role = await self._role_repo.get_by_name(default_role_name)
        if default_role is not None:
            initial_roles.append(default_role)

        # 5. Instantiate and persist User entity
        new_user = User(
            email=normalized_email,
            hashed_password=hashed_password,
            full_name=request.full_name.strip(),
            roles=initial_roles,
        )
        created_user = await self._user_repo.create(new_user)

        # 6. Commit transaction boundary
        await self._session.commit()

        logger.info(
            "user_registration_completed",
            user_id=str(created_user.id),
            email=created_user.email,
        )

        return UserResponse(
            id=created_user.id,
            email=created_user.email,
            full_name=created_user.full_name,
            is_active=created_user.is_active,
            is_verified=created_user.is_verified,
            is_superuser=created_user.is_superuser,
            roles=created_user.role_names,
            created_at=created_user.created_at,
            last_login_at=created_user.last_login_at,
        )

    async def authenticate(self, request: UserLoginRequest) -> TokenResponse:
        """Authenticate user credentials and issue an authorized JWT token pair.

        Features constant-time dummy verification to defeat account enumeration attacks.

        Args:
            request: Login payload containing email and plaintext password.

        Returns:
            TokenResponse: Synchronized access and refresh tokens.

        Raises:
            UnauthorizedException: If email or password is invalid (generic message).
            ForbiddenException: If user account is inactive or soft-deleted.
        """
        normalized_email = request.email.strip().lower()

        # 1. Fetch user with eagerly-loaded roles and permissions in one query
        user = await self._user_repo.get_by_email_with_roles_and_permissions(
            email=normalized_email, include_deleted=True
        )

        # 2. Timing attack mitigation: verify dummy hash if user does not exist
        if user is None:
            await async_verify_password(
                plain_password=request.password, hashed_password=self.DUMMY_ARGON2_HASH
            )
            logger.warning(
                "authentication_failed",
                reason="user_not_found",
                email=normalized_email,
            )
            raise UnauthorizedException(message="Invalid email or password.")

        # 3. Verify actual Argon2id password hash
        is_password_valid = await async_verify_password(
            plain_password=request.password, hashed_password=user.hashed_password
        )
        if not is_password_valid:
            logger.warning(
                "authentication_failed",
                reason="invalid_password",
                user_id=str(user.id),
            )
            raise UnauthorizedException(message="Invalid email or password.")

        # 4. Enforce account status invariants
        if user.is_deleted or not user.is_active:
            logger.warning(
                "authentication_rejected",
                reason="account_inactive_or_deleted",
                user_id=str(user.id),
            )
            raise ForbiddenException(
                message="User account is deactivated or suspended.",
                details={"user_id": str(user.id)},
            )

        # 5. Update last_login_at timestamp & commit transaction
        await self._user_repo.update_last_login(user.id)
        await self._session.commit()

        # 6. Issue token pair with security claims
        token_pair = self._token_service.issue_token_pair_for_user(user)

        logger.info(
            "authentication_successful",
            user_id=str(user.id),
            email=user.email,
        )

        return TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type="Bearer",
            expires_in=token_pair.expires_in,
        )

    async def refresh_access_token(
        self, request: RefreshTokenRequest
    ) -> TokenResponse:
        """Issue a new token pair using a valid cryptographic refresh token (rotation).

        Args:
            request: Refresh payload containing the active refresh token.

        Returns:
            TokenResponse: Newly rotated access and refresh tokens.

        Raises:
            UnauthorizedException: If refresh token is expired or malformed.
            ForbiddenException: If user account has been disabled.
        """
        # 1. Decode and validate refresh token signature and type
        payload = self._token_service.validate_refresh_token(request.refresh_token)

        # 2. Parse subject UUID
        try:
            user_id = uuid.UUID(payload.sub)
        except ValueError as exc:
            raise UnauthorizedException(
                message="Malformed subject identifier in token payload."
            ) from exc

        # 3. Retrieve user with fresh roles and permissions
        user = await self._user_repo.get_with_roles_and_permissions(user_id)
        active_user = IdentityValidators.ensure_user_is_active(user)

        # 4. Issue rotated token pair
        token_pair = self._token_service.issue_token_pair_for_user(active_user)

        logger.info(
            "token_refresh_successful",
            user_id=str(active_user.id),
        )

        return TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type="Bearer",
            expires_in=token_pair.expires_in,
        )
