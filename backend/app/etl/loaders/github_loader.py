"""GitHub Repository ETL Loader for Investiga (Placeholder).

Exposes the BaseLoader contract for ingesting Git repositories, branches,
and pull requests via GitHub REST / GraphQL APIs.
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


class GitHubLoader(BaseLoader):
    """GitHub repository data loader (Interface Placeholder)."""

    SOURCE_TYPE: ClassVar[ETLSource] = ETLSource.GITHUB

    async def discover(
        self,
        config: ETLConfiguration,
    ) -> AsyncIterator[ETLDiscoveredItem]:
        """Discover files in remote GitHub repository (Placeholder)."""
        if False:
            yield ETLDiscoveredItem(
                source_uri="", relative_path="", filename="", extension=""
            )
        raise NotImplementedError(
            "GitHubLoader is a placeholder and not yet implemented. "
            "Future iterations will support GitHub API authentication, branch discovery, and webhook triggers."
        )

    async def load(
        self,
        item: ETLDiscoveredItem,
        config: ETLConfiguration,
    ) -> ETLDocumentStreamItem:
        """Download file payload from GitHub repository (Placeholder)."""
        raise NotImplementedError(
            "GitHubLoader is a placeholder and not yet implemented."
        )

    async def health_check(self) -> bool:
        """Check reachability of GitHub API."""
        return True
