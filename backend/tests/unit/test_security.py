"""Unit tests for the Security and Cryptography Infrastructure."""

from datetime import timedelta

import pytest

from app.core.security import (
    async_get_password_hash,
    async_verify_password,
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.exceptions import UnauthorizedException


def test_password_hashing_and_verification() -> None:
    raw_password = "InvestigaSecurePassword2026!"
    hashed = get_password_hash(raw_password)

    assert hashed != raw_password
    assert hashed.startswith("$argon2")

    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword123", hashed) is False
    assert verify_password("", hashed) is False


@pytest.mark.asyncio
async def test_async_password_hashing() -> None:
    raw_password = "AsyncOffloadedPasswordVerification#1"
    hashed = await async_get_password_hash(raw_password)

    assert verify_password(raw_password, hashed) is True
    verified = await async_verify_password(raw_password, hashed)
    assert verified is True

    rejected = await async_verify_password("IncorrectGuess", hashed)
    assert rejected is False


def test_access_token_creation_and_decoding() -> None:
    user_id = "user-uuid-984b-4c0a"
    roles = ["admin", "incident_responder"]
    permissions = ["investigations:create", "investigations:read"]

    token = create_access_token(
        subject=user_id,
        roles=roles,
        permissions=permissions,
        custom_claims={"tenant_id": "tenant-001"},
    )

    payload = decode_token(token=token, expected_type="access")
    assert payload.sub == user_id
    assert payload.token_type == "access"
    assert payload.roles == roles
    assert payload.permissions == permissions
    assert payload.custom_claims.get("tenant_id") == "tenant-001"
    assert payload.iss == "Investiga"
    assert payload.jti is not None
    assert payload.exp > payload.iat


def test_refresh_token_creation_and_decoding() -> None:
    user_id = "user-uuid-refresh-test"
    token = create_refresh_token(subject=user_id)

    payload = decode_token(token=token, expected_type="refresh")
    assert payload.sub == user_id
    assert payload.token_type == "refresh"


def test_token_pair_creation() -> None:
    user_id = "user-uuid-pair-test"
    pair = create_token_pair(
        subject=user_id,
        roles=["analyst"],
    )

    assert pair.token_type == "bearer"
    assert pair.expires_in > 0

    access_payload = decode_token(pair.access_token, expected_type="access")
    assert access_payload.sub == user_id
    assert access_payload.token_type == "access"

    refresh_payload = decode_token(pair.refresh_token, expected_type="refresh")
    assert refresh_payload.sub == user_id
    assert refresh_payload.token_type == "refresh"


def test_token_expiration_validation() -> None:
    user_id = "user-uuid-expired"
    # Issue a token expired 10 seconds ago
    expired_token = create_access_token(
        subject=user_id,
        expires_delta=timedelta(seconds=-10),
    )

    with pytest.raises(UnauthorizedException) as exc_info:
        decode_token(token=expired_token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.details.get("error_subcode") == "TOKEN_EXPIRED"


def test_invalid_signature_validation() -> None:
    user_id = "user-uuid-tampered"
    valid_token = create_access_token(subject=user_id)

    # Tamper with token signature
    tampered_token = valid_token[:-4] + "abcd"

    with pytest.raises(UnauthorizedException) as exc_info:
        decode_token(token=tampered_token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.details.get("error_subcode") == "INVALID_TOKEN"


def test_token_type_mismatch_validation() -> None:
    user_id = "user-uuid-mismatch"
    refresh_token = create_refresh_token(subject=user_id)

    # Attempt to validate a refresh token as an access token
    with pytest.raises(UnauthorizedException) as exc_info:
        decode_token(token=refresh_token, expected_type="access")

    assert exc_info.value.status_code == 401
    assert exc_info.value.details.get("error_subcode") == "INVALID_TOKEN_TYPE"


def test_malformed_token_validation() -> None:
    with pytest.raises(UnauthorizedException) as exc_info:
        decode_token(token="completely-malformed-token-string")

    assert exc_info.value.status_code == 401
    assert exc_info.value.details.get("error_subcode") == "INVALID_TOKEN"
