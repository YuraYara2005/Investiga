"""JSON Web Token (JWT) Infrastructure for Investiga.

This module provides cryptographic token issuance, decoding, signature validation,
and expiration enforcement using Python-Jose and Pydantic Settings.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.tokens import TokenPair, TokenPayload, TokenType
from app.exceptions import UnauthorizedException

logger = get_logger(__name__)


def create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta | None = None,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
    custom_claims: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> str:
    """Issue a signed cryptographic JWT token conforming to RFC 7519 standards.

    Args:
        subject: Subject identifier (User UUID).
        token_type: Token discriminator ('access' or 'refresh').
        expires_delta: Custom expiration delta. If None, default lifespan from settings is applied.
        roles: Optional user roles.
        permissions: Optional permission codes.
        custom_claims: Optional dictionary of domain-specific claims.
        settings: Application settings. If None, loaded via `get_settings()`.

    Returns:
        str: Encoded, signed JWT string.
    """
    if settings is None:
        settings = get_settings()

    now = datetime.now(UTC)

    if expires_delta is not None:
        expire = now + expires_delta
    elif token_type == "access":
        expire = now + timedelta(minutes=settings.security.access_token_expire_minutes)
    else:  # refresh
        expire = now + timedelta(days=settings.security.refresh_token_expire_days)

    jti = str(uuid.uuid4())
    claims: dict[str, Any] = {
        "sub": subject,
        "jti": jti,
        "token_type": token_type,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": settings.app.name,
        "roles": roles or [],
        "permissions": permissions or [],
        "custom_claims": custom_claims or {},
    }

    secret_key = settings.security.secret_key.get_secret_value()
    encoded_jwt = jwt.encode(
        claims,
        secret_key,
        algorithm=settings.security.algorithm,
    )

    logger.info(
        "jwt_token_issued",
        subject=subject,
        token_type=token_type,
        jti=jti,
        expires_at=expire.isoformat(),
    )

    return encoded_jwt


def create_access_token(
    subject: str,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
    custom_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
    settings: Settings | None = None,
) -> str:
    """Issue a short-lived access token for API authorization."""
    return create_token(
        subject=subject,
        token_type="access",
        expires_delta=expires_delta,
        roles=roles,
        permissions=permissions,
        custom_claims=custom_claims,
        settings=settings,
    )


def create_refresh_token(
    subject: str,
    expires_delta: timedelta | None = None,
    settings: Settings | None = None,
) -> str:
    """Issue a long-lived refresh token for token rotation."""
    return create_token(
        subject=subject,
        token_type="refresh",
        expires_delta=expires_delta,
        settings=settings,
    )


def create_token_pair(
    subject: str,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
    custom_claims: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> TokenPair:
    """Issue a synchronized pair of access and refresh tokens.

    Args:
        subject: Subject identifier (User UUID).
        roles: Optional assigned user roles.
        permissions: Optional fine-grained permissions.
        custom_claims: Optional custom claims.
        settings: Application settings.

    Returns:
        TokenPair: Structured response containing both tokens and expiration duration.
    """
    if settings is None:
        settings = get_settings()

    access_token = create_access_token(
        subject=subject,
        roles=roles,
        permissions=permissions,
        custom_claims=custom_claims,
        settings=settings,
    )

    refresh_token = create_refresh_token(
        subject=subject,
        settings=settings,
    )

    expires_in = settings.security.access_token_expire_minutes * 60

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
    )


def decode_token(
    token: str,
    expected_type: TokenType | None = None,
    settings: Settings | None = None,
) -> TokenPayload:
    """Decode, verify signature, and validate claims of an incoming JWT string.

    Args:
        token: Raw JWT string extracted from Authorization header.
        expected_type: Optional expected token type ('access' or 'refresh').
        settings: Application settings.

    Returns:
        TokenPayload: Validated and typed token claims model.

    Raises:
        UnauthorizedException: If token is expired, signature is invalid, or claims are malformed.
    """
    if settings is None:
        settings = get_settings()

    secret_key = settings.security.secret_key.get_secret_value()

    try:
        raw_payload = jwt.decode(
            token,
            secret_key,
            algorithms=[settings.security.algorithm],
            issuer=settings.app.name,
        )
    except ExpiredSignatureError as exc:
        logger.warning("jwt_token_validation_failed", reason="token_expired")
        raise UnauthorizedException(
            message="Authentication token has expired. Please refresh your session.",
            details={"error_subcode": "TOKEN_EXPIRED"},
        ) from exc
    except JWTError as exc:
        logger.warning(
            "jwt_token_validation_failed",
            reason="invalid_signature_or_format",
            error=str(exc),
        )
        raise UnauthorizedException(
            message="Invalid authentication token signature or malformed token.",
            details={"error_subcode": "INVALID_TOKEN"},
        ) from exc

    try:
        payload = TokenPayload.model_validate(raw_payload)
    except Exception as exc:
        logger.error(
            "jwt_payload_schema_validation_failed",
            error=str(exc),
            exc_info=True,
        )
        raise UnauthorizedException(
            message="Token payload schema validation failed.",
            details={"error_subcode": "MALFORMED_TOKEN_PAYLOAD"},
        ) from exc

    if expected_type is not None and payload.token_type != expected_type:
        logger.warning(
            "jwt_token_type_mismatch",
            expected=expected_type,
            received=payload.token_type,
            subject=payload.sub,
        )
        raise UnauthorizedException(
            message=f"Invalid token type: expected '{expected_type}', got '{payload.token_type}'.",
            details={"error_subcode": "INVALID_TOKEN_TYPE"},
        )

    return payload
