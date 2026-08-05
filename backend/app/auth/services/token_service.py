"""Token Management Service for Investiga.

This module encapsulates token issuance, verification, and rotation routines
building on top of the low-level cryptographic JWT infrastructure.
"""

from typing import Any

from app.auth.models import User
from app.core.config import Settings, get_settings
from app.core.jwt import create_token_pair, decode_token
from app.core.tokens import TokenPair, TokenPayload


class TokenService:
    """Service orchestrating JWT lifecycle, token issuance, and rotation."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def issue_token_pair_for_user(
        self, user: User, custom_claims: dict[str, Any] | None = None
    ) -> TokenPair:
        """Issue a synchronized Access + Refresh token pair populated with user claims.

        Args:
            user: Authenticated active User entity.
            custom_claims: Optional extra claims dictionary.

        Returns:
            TokenPair: Access token, Refresh token, and expiry metadata.
        """
        return create_token_pair(
            subject=str(user.id),
            roles=user.role_names,
            permissions=list(user.permission_codes),
            custom_claims=custom_claims,
            settings=self._settings,
        )

    def validate_refresh_token(self, refresh_token: str) -> TokenPayload:
        """Validate an incoming refresh token string.

        Args:
            refresh_token: Raw JWT refresh token string.

        Returns:
            TokenPayload: Validated refresh token claims.

        Raises:
            UnauthorizedException: If token is expired, invalid, or wrong type.
        """
        return decode_token(
            token=refresh_token,
            expected_type="refresh",
            settings=self._settings,
        )

    def validate_access_token(self, access_token: str) -> TokenPayload:
        """Validate an incoming access token string.

        Args:
            access_token: Raw JWT bearer access token string.

        Returns:
            TokenPayload: Validated access token claims.

        Raises:
            UnauthorizedException: If token is expired, invalid, or wrong type.
        """
        return decode_token(
            token=access_token,
            expected_type="access",
            settings=self._settings,
        )
