"""REST / Generic API ETL Loader for Investiga (Placeholder).

Exposes the BaseLoader contract for ingesting structured JSON/XML payloads,
OpenAPI specs, and paginated REST data endpoints.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import ClassVar

from app.etl.loaders.base_loader import BaseLoader
from app.etl.models import (
    ETLConfiguration,
    ETLDiscoveredItem,
    ETLDocumentStreamItem,
    ETLSource,
)


class APILoader(BaseLoader):
    """Generic REST API Data Loader (Interface Placeholder)."""

    SOURCE_TYPE: ClassVar[ETLSource] = ETLSource.API

    async def discover(
        self,
        config: ETLConfiguration,
    ) -> AsyncIterator[ETLDiscoveredItem]:
        """Discover endpoints and records via HTTP API (Placeholder)."""
        if False:
            yield ETLDiscoveredItem(
                source_uri="", relative_path="", filename="", extension=""
            )
        raise NotImplementedError(
            "APILoader is a placeholder and not yet implemented. "
            "Future iterations will support auth tokens, header injection, pagination, and JSON/XML mapping."
        )

    async def load(
        self,
        item: ETLDiscoveredItem,
        config: ETLConfiguration,
    ) -> ETLDocumentStreamItem:
        """Fetch endpoint content (Placeholder)."""
        raise NotImplementedError("APILoader is a placeholder and not yet implemented.")

    async def health_check(self) -> bool:
        """Check API endpoint connectivity."""
        return True
