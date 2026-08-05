"""Identity Business Validators for Investiga.

This module encapsulates domain rule assertions (e.g., duplicate email rejection,
account active status, credential checks) raising standardized domain exceptions.
"""

from app.auth.models import User
from app.auth.repositories.interfaces import IUserRepository
from app.auth.services.password_policy import PasswordPolicy, default_password_policy
from app.exceptions.domain import (
    ConflictException,
    ForbiddenException,
    UnauthorizedException,
)


class IdentityValidators:
    """Encapsulates reusable domain validation assertions for identity operations."""

    @staticmethod
    async def ensure_email_is_available(user_repo: IUserRepository, email: str) -> None:
        """Verify that an email address is not already registered to an active account.

        Args:
            user_repo: User data access repository.
            email: Candidate email address to check.

        Raises:
            ConflictException: If the email is already in use.
        """
        if await user_repo.email_exists(email):
            raise ConflictException(
                message="An account with this email address already exists.",
                details={"email": email},
            )

    @staticmethod
    def ensure_user_is_active(user: User | None) -> User:
        """Verify that a user exists, is not soft-deleted, and has active status.

        Args:
            user: User entity instance or None.

        Returns:
            User: The validated active user entity.

        Raises:
            UnauthorizedException: If user is None (generic message for auth flows).
            ForbiddenException: If user account has been disabled or soft-deleted.
        """
        if user is None:
            raise UnauthorizedException(message="Invalid email or password.")

        if user.is_deleted or not user.is_active:
            raise ForbiddenException(
                message="User account has been deactivated or suspended.",
                details={"user_id": str(user.id)},
            )

        return user

    @staticmethod
    def validate_password_complexity(
        password: str, policy: PasswordPolicy = default_password_policy
    ) -> None:
        """Validate a plaintext password against the specified password policy.

        Args:
            password: Candidate plaintext password string.
            policy: The PasswordPolicy instance to evaluate against.
        """
        policy.validate(password)
