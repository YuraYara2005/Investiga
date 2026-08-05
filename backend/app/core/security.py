"""Security and Cryptographic Infrastructure Facade for Investiga.

This module provides a unified public interface exposing password hashing,
Argon2 verification, JWT encoding/decoding, and token payload models.
"""

from app.core.jwt import (
    create_access_token,
    create_refresh_token,
    create_token,
    create_token_pair,
    decode_token,
)
from app.core.password import (
    async_get_password_hash,
    async_verify_password,
    get_password_hash,
    needs_rehash,
    verify_password,
)
from app.core.tokens import TokenPair, TokenPayload, TokenType

__all__ = [
    "TokenPair",
    "TokenPayload",
    "TokenType",
    "async_get_password_hash",
    "async_verify_password",
    "create_access_token",
    "create_refresh_token",
    "create_token",
    "create_token_pair",
    "decode_token",
    "get_password_hash",
    "needs_rehash",
    "verify_password",
]
