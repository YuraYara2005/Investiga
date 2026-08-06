"""Atlassian Confluence ETL Loader for Investiga (Placeholder).

Exposes the BaseLoader contract for connecting to Atlassian Cloud / Data Center REST API
to sync spaces, page hierarchies, attachments, and knowledge bases.
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


class ConfluenceLoader(BaseLoader):
    """Atlassian Confluence Space & Page loader (Interface Placeholder)."""

    SOURCE_TYPE: ClassVar[ETLSource] = ETLSource.CONFLUENCE

    async def discover(
        self,
        config: ETLConfiguration,
    ) -> AsyncIterator[ETLDiscoveredItem]:
        """Discover pages within Confluence spaces (Placeholder)."""
        if False:
            yield ETLDiscoveredItem(
                source_uri="", relative_path="", filename="", extension=""
            )
        raise NotImplementedError(
            "ConfluenceLoader is a placeholder and not yet implemented. "
            "Future iterations will support Atlassian API tokens, space keys, and CQL queries."
        )

    async def load(
        self,
        item: ETLDiscoveredItem,
        config: ETLConfiguration,
    ) -> ETLDocumentStreamItem:
        """Fetch Confluence page content and convert storage format HTML (Placeholder)."""
        raise NotImplementedError(
            "ConfluenceLoader is a placeholder and not yet implemented."
        )

    async def health_check(self) -> bool:
        """Check Atlassian Confluence reachability."""
        return True
