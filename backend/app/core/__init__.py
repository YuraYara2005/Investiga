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

__all__ = [
    "Settings",
    "get_settings",
    "lifespan",
    "setup_logging",
    "get_logger",
    "bind_request_context",
    "unbind_request_context",
    "clear_request_context",
]


