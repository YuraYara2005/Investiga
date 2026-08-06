"""Notion Knowledge Base ETL Loader for Investiga (Placeholder).

Exposes the BaseLoader contract for querying Notion Databases, Pages, and Blocks
via Notion official REST API.
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


class NotionLoader(BaseLoader):
    """Notion Workspace loader (Interface Placeholder)."""

    SOURCE_TYPE: ClassVar[ETLSource] = ETLSource.NOTION

    async def discover(
        self,
        config: ETLConfiguration,
    ) -> AsyncIterator[ETLDiscoveredItem]:
        """Discover Notion databases and pages (Placeholder)."""
        if False:
            yield ETLDiscoveredItem(
                source_uri="", relative_path="", filename="", extension=""
            )
        raise NotImplementedError(
            "NotionLoader is a placeholder and not yet implemented. "
            "Future iterations will support Notion Integration Tokens and block parsing."
        )

    async def load(
        self,
        item: ETLDiscoveredItem,
        config: ETLConfiguration,
    ) -> ETLDocumentStreamItem:
        """Fetch and serialize Notion page content into Markdown (Placeholder)."""
        raise NotImplementedError(
            "NotionLoader is a placeholder and not yet implemented."
        )

    async def health_check(self) -> bool:
        """Check Notion API reachability."""
        return True
