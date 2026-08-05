"""Enterprise Structured Logging Subsystem for Investiga.

This module establishes a unified, async-safe, context-aware logging pipeline
powered by Structlog and Python's standard logging library. It supports dynamic
context variable binding (e.g., request_id, user_id, latency_ms), automated
sensitive data redaction, and environment-driven formatting (colored console for
local development vs. high-throughput structured JSON for production/Kubernetes).
"""

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.core.config import Settings, get_settings

# Set of case-insensitive substring patterns that must be redacted from all log payloads
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "secret_key",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "authorization",
        "auth_token",
        "private_key",
        "client_secret",
        "cookie",
        "session_id",
    }
)

REDACTED_SENTINEL: str = "[REDACTED]"


class RedactSensitiveDataProcessor:
    """Processor to recursively sanitize sensitive data across event dictionaries.

    Inspects both top-level and nested key-value pairs, masking matching sensitive
    keys with `[REDACTED]` to prevent credential leakage into log aggregators.
    """

    def __init__(self, sensitive_keys: frozenset[str] = SENSITIVE_KEYS) -> None:
        self.sensitive_keys = sensitive_keys

    def _sanitize_mapping(self, data: MutableMapping[str, Any]) -> None:
        for key in list(data.keys()):
            val = data[key]
            lower_key = str(key).lower()
            if any(s in lower_key for s in self.sensitive_keys):
                data[key] = REDACTED_SENTINEL
            elif isinstance(val, MutableMapping):
                self._sanitize_mapping(val)
            elif isinstance(val, (list, tuple, set)):
                data[key] = [
                    self._sanitize_item(item) for item in val
                ]

    def _sanitize_item(self, item: Any) -> Any:
        if isinstance(item, MutableMapping):
            item_copy = dict(item)
            self._sanitize_mapping(item_copy)
            return item_copy
        elif isinstance(item, (list, tuple, set)):
            return [self._sanitize_item(sub) for sub in item]
        return item

    def __call__(
        self, logger: logging.Logger, name: str, event_dict: EventDict
    ) -> EventDict:
        self._sanitize_mapping(event_dict)
        return event_dict


class ApplicationMetadataProcessor:
    """Processor to inject static application metadata into all log records."""

    def __init__(self, settings: Settings) -> None:
        self.metadata = {
            "app_name": settings.app.name,
            "environment": settings.app.environment,
            "version": settings.app.version,
        }

    def __call__(
        self, logger: logging.Logger, name: str, event_dict: EventDict
    ) -> EventDict:
        event_dict.update(self.metadata)
        return event_dict


def setup_logging(settings: Settings | None = None) -> None:
    """Configure Structlog and synchronize Python's standard library logging.

    Establishes a unified logging pipeline where all standard library loggers
    (Uvicorn, SQLAlchemy, AsyncPG, Third-Party) and application loggers route
    through the exact same formatting, contextual enrichment, and redaction rules.

    Args:
        settings: Application settings. If None, loaded via `get_settings()`.
    """
    if settings is None:
        settings = get_settings()

    log_level = getattr(logging, settings.logging.log_level.upper(), logging.INFO)

    # Base processors applied across both structlog and standard library log entries
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        ApplicationMetadataProcessor(settings=settings),
        RedactSensitiveDataProcessor(),
    ]

    if settings.logging.json_logs:
        # Production JSON renderer for Datadog / Elasticsearch / CloudWatch
        final_renderer: Processor = structlog.processors.JSONRenderer()
    else:
        # Local development colored console renderer
        final_renderer = structlog.dev.ConsoleRenderer(
            colors=sys.stdout.isatty(),
            pad_event=30,
        )

    # Configure Structlog core engine
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure Standard Library Formatter to use Structlog processor pipeline
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            final_renderer,
        ],
    )

    # Attach handler to root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Align standard third-party loggers with the configured log level
    for logger_name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "fastapi",
        "sqlalchemy.engine",
        "asyncpg",
    ):
        target_logger = logging.getLogger(logger_name)
        target_logger.handlers.clear()
        target_logger.propagate = True
        target_logger.setLevel(log_level)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Obtain a type-safe, context-aware structured logger instance.

    Args:
        name: Subsystem or module name (typically `__name__`).

    Returns:
        structlog.stdlib.BoundLogger: Configured structured logger.
    """
    return structlog.stdlib.get_logger(name)


def bind_request_context(**kwargs: Any) -> None:
    """Bind contextual attributes to the current asynchronous task execution context.

    Values bound via this function (e.g., request_id, user_id, route) will be
    automatically attached to all subsequent logs emitted within this coroutine.

    Args:
        **kwargs: Key-value pairs to bind into contextvars.
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_request_context(*keys: str) -> None:
    """Unbind specific keys from the current asynchronous task execution context.

    Args:
        *keys: Keys to remove from contextvars.
    """
    structlog.contextvars.unbind_contextvars(*keys)


def clear_request_context() -> None:
    """Clear all contextual variables for the current asynchronous task.

    Must be invoked at the end of each HTTP request/worker cycle to avoid
    context leakage across recycled event loop tasks.
    """
    structlog.contextvars.clear_contextvars()
