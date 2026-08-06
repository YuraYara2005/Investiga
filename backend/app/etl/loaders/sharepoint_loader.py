"""Microsoft SharePoint / OneDrive ETL Loader for Investiga (Placeholder).

Exposes the BaseLoader contract for connecting to Microsoft Graph API and syncing
enterprise SharePoint document libraries and folders.
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


class SharePointLoader(BaseLoader):
    """Microsoft SharePoint document library loader (Interface Placeholder)."""

    SOURCE_TYPE: ClassVar[ETLSource] = ETLSource.SHAREPOINT

    async def discover(
        self,
        config: ETLConfiguration,
    ) -> AsyncIterator[ETLDiscoveredItem]:
        """Discover documents in SharePoint site libraries (Placeholder)."""
        if False:
            yield ETLDiscoveredItem(
                source_uri="", relative_path="", filename="", extension=""
            )
        raise NotImplementedError(
            "SharePointLoader is a placeholder and not yet implemented. "
            "Future iterations will support Microsoft Graph OAuth2, tenant IDs, and drive discovery."
        )

    async def load(
        self,
        item: ETLDiscoveredItem,
        config: ETLConfiguration,
    ) -> ETLDocumentStreamItem:
        """Download document from SharePoint via Microsoft Graph (Placeholder)."""
        raise NotImplementedError(
            "SharePointLoader is a placeholder and not yet implemented."
        )

    async def health_check(self) -> bool:
        """Check Microsoft Graph reachability."""
        return True
