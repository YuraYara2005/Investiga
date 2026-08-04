"""Core package initialization for Investiga backend.

Provides fundamental primitives, configuration, logging, security, and lifecycle management.
"""

from app.core.config import Settings, get_settings
from app.core.lifespan import lifespan
from app.core.logging import (
    bind_request_context,
    clear_request_context,
    get_logger,
    setup_logging,
    unbind_request_context,
)
from app.core.security import (
    TokenPair,
    TokenPayload,
    TokenType,
    async_get_password_hash,
    async_verify_password,
    create_access_token,
    create_refresh_token,
    create_token,
    create_token_pair,
    decode_token,
    get_password_hash,
    needs_rehash,
    verify_password,
)

__all__ = [
    "Settings",
    "get_settings",
    "lifespan",
    "setup_logging",
    "get_logger",
    "bind_request_context",
    "unbind_request_context",
    "clear_request_context",
    "get_password_hash",
    "verify_password",
    "needs_rehash",
    "async_get_password_hash",
    "async_verify_password",
    "create_token",
    "create_access_token",
    "create_refresh_token",
    "create_token_pair",
    "decode_token",
    "TokenType",
    "TokenPayload",
    "TokenPair",
]



