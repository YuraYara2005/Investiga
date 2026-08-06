"""Google Drive ETL Loader for Investiga (Placeholder).

Exposes the BaseLoader contract for connecting to Google Drive API v3 and syncing
shared team drives, folder hierarchies, and Google Workspace docs.
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


class GDriveLoader(BaseLoader):
    """Google Drive document loader (Interface Placeholder)."""

    SOURCE_TYPE: ClassVar[ETLSource] = ETLSource.GDRIVE

    async def discover(
        self,
        config: ETLConfiguration,
    ) -> AsyncIterator[ETLDiscoveredItem]:
        """Discover files and folders in Google Drive (Placeholder)."""
        if False:
            yield ETLDiscoveredItem(
                source_uri="", relative_path="", filename="", extension=""
            )
        raise NotImplementedError(
            "GDriveLoader is a placeholder and not yet implemented. "
            "Future iterations will support Google Service Account OAuth2 and Google Drive API v3."
        )

    async def load(
        self,
        item: ETLDiscoveredItem,
        config: ETLConfiguration,
    ) -> ETLDocumentStreamItem:
        """Download binary payload or export Google Doc (Placeholder)."""
        raise NotImplementedError(
            "GDriveLoader is a placeholder and not yet implemented."
        )

    async def health_check(self) -> bool:
        """Check Google Drive API reachability."""
        return True
