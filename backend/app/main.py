"""Main FastAPI Application Entry Point for Investiga.

This module provides the enterprise Application Factory `create_app()` which
configures the ASGI server, lifespan lifecycle manager, CORS security policies,
structured request-correlation middleware, centralized exception handlers, and
versioned API routing.
"""

import time
import uuid

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.api.router import root_api_router
from app.core.config import Settings, get_settings
from app.core.lifespan import lifespan
from app.core.logging import (
    bind_request_context,
    clear_request_context,
    get_logger,
)
from app.exceptions import register_exception_handlers

logger = get_logger(__name__)


class RequestCorrelationAndLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to inject request correlation IDs and measure execution latency."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # 1. Extract or generate unique correlation Request ID
        request_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:12]}"
        request.state.request_id = request_id

        # 2. Extract Client IP
        client_ip = request.client.host if request.client else "unknown"

        # 3. Bind async context variables for structured logs
        bind_request_context(
            request_id=request_id,
            client_ip=client_ip,
            http_method=request.method,
            path=str(request.url.path),
        )

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            process_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # 4. Attach diagnostic headers to outgoing response
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time-Ms"] = str(process_time_ms)

            logger.info(
                "http_request_completed",
                status_code=response.status_code,
                duration_ms=process_time_ms,
            )

            return response
        except Exception as exc:
            process_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                "http_request_failed_unhandled",
                error=str(exc),
                duration_ms=process_time_ms,
                exc_info=True,
            )
            raise
        finally:
            # 5. Guaranteed cleanup of context variables
            clear_request_context()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application Factory to instantiate and configure the Investiga FastAPI platform.

    Args:
        settings: Application configuration. If None, loaded via `get_settings()`.

    Returns:
        FastAPI: Fully configured ASGI application instance.
    """
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=f"{settings.app.name} API",
        summary=settings.app.tagline,
        description=(
            "Enterprise platform that assists engineers in investigating operational incidents "
            "combining knowledge management, hybrid retrieval, LLM reasoning, and analytics."
        ),
        version=settings.app.version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=[
            {
                "name": "Health & Monitoring",
                "description": "Liveness, readiness, and diagnostic health probes.",
            },
        ],
    )

    # 1. Cross-Origin Resource Sharing (CORS) Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.allow_origins,
        allow_credentials=settings.cors.allow_credentials,
        allow_methods=settings.cors.allow_methods,
        allow_headers=settings.cors.allow_headers,
    )

    # 2. Request Correlation & Observability Middleware
    app.add_middleware(RequestCorrelationAndLoggingMiddleware)

    # 3. Centralized Exception Handlers
    register_exception_handlers(app)

    # 4. Versioned API Routing
    app.include_router(root_api_router)

    return app


# Root ASGI Application Instance
app = create_app()

if __name__ == "__main__":
    current_settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=current_settings.server.host,
        port=current_settings.server.port,
        reload=current_settings.server.reload,
        workers=current_settings.server.workers,
    )
