"""Core package initialization for Investiga backend.

Provides fundamental primitives, configuration, logging, security, and lifecycle management.
"""

from app.core.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
