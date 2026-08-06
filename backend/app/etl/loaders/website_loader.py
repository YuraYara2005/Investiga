"""Technical Website / Documentation Crawler ETL Loader for Investiga (Placeholder).

Exposes the BaseLoader contract for recursive HTTP/HTTPS crawling of documentation portals,
HTML sitemaps, and web knowledge bases.
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


class WebsiteLoader(BaseLoader):
    """Technical Documentation Website Loader (Interface Placeholder)."""

    SOURCE_TYPE: ClassVar[ETLSource] = ETLSource.WEBSITE

    async def discover(
        self,
        config: ETLConfiguration,
    ) -> AsyncIterator[ETLDiscoveredItem]:
        """Crawl website sitemaps and pages (Placeholder)."""
        if False:
            yield ETLDiscoveredItem(
                source_uri="", relative_path="", filename="", extension=""
            )
        raise NotImplementedError(
            "WebsiteLoader is a placeholder and not yet implemented. "
            "Future iterations will support sitemap parsing, domain boundaries, and depth-limited crawling."
        )

    async def load(
        self,
        item: ETLDiscoveredItem,
        config: ETLConfiguration,
    ) -> ETLDocumentStreamItem:
        """Fetch remote HTML page payload (Placeholder)."""
        raise NotImplementedError(
            "WebsiteLoader is a placeholder and not yet implemented."
        )

    async def health_check(self) -> bool:
        """Check web connectivity."""
        return True
