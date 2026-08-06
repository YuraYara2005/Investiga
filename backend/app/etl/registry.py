"""ETL Loader Factory and Discovery Registry for Investiga.

Provides centralized registration, lookup, and lifecycle management for
all ETL source loader implementations.
"""

from __future__ import annotations

from functools import lru_cache
from typing import ClassVar

from app.core.logging import get_logger
from app.etl.exceptions import ETLUnsupportedSourceException
from app.etl.interfaces import BaseLoaderInterface, ETLRegistryInterface
from app.etl.loaders.api_loader import APILoader
from app.etl.loaders.confluence_loader import ConfluenceLoader
from app.etl.loaders.filesystem_loader import FilesystemLoader
from app.etl.loaders.gdrive_loader import GDriveLoader
from app.etl.loaders.github_loader import GitHubLoader
from app.etl.loaders.notion_loader import NotionLoader
from app.etl.loaders.sharepoint_loader import SharePointLoader
from app.etl.loaders.website_loader import WebsiteLoader
from app.etl.models import ETLSource

logger = get_logger(__name__)


class LoaderRegistry(ETLRegistryInterface):
    """Thread-safe registry mapping ETL source identifiers to loader instances."""

    _DEFAULT_LOADERS: ClassVar[dict[ETLSource, type[BaseLoaderInterface]]] = {
        ETLSource.FILESYSTEM: FilesystemLoader,
        ETLSource.GITHUB: GitHubLoader,
        ETLSource.WEBSITE: WebsiteLoader,
        ETLSource.API: APILoader,
        ETLSource.SHAREPOINT: SharePointLoader,
        ETLSource.GDRIVE: GDriveLoader,
        ETLSource.NOTION: NotionLoader,
        ETLSource.CONFLUENCE: ConfluenceLoader,
    }

    def __init__(self) -> None:
        """Initialize registry and populate default loaders."""
        self._loaders: dict[ETLSource, BaseLoaderInterface] = {}
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Instantiate default registered loader classes."""
        for source_enum, loader_cls in self._DEFAULT_LOADERS.items():
            self._loaders[source_enum] = loader_cls()

    def register(
        self,
        source: ETLSource,
        loader: BaseLoaderInterface,
    ) -> None:
        """Register or override a loader instance for a source type.

        Args:
            source: ETLSource identifier enum.
            loader: BaseLoaderInterface instance.
        """
        self._loaders[source] = loader
        logger.info(
            "etl_loader_registered",
            source=source.value,
            loader_class=loader.__class__.__name__,
        )

    def get(self, source: ETLSource | str) -> BaseLoaderInterface:
        """Retrieve the loader registered for the requested source.

        Args:
            source: ETLSource enum or string identifier.

        Returns:
            BaseLoaderInterface: Configured loader instance.

        Raises:
            ETLUnsupportedSourceException: If source is unregistered.
        """
        try:
            source_enum = ETLSource(source) if isinstance(source, str) else source
        except ValueError:
            raise ETLUnsupportedSourceException(
                source=str(source),
                details={"registered_sources": [s.value for s in self._loaders]},
            ) from None

        if source_enum not in self._loaders:
            raise ETLUnsupportedSourceException(
                source=source_enum.value,
                details={"registered_sources": [s.value for s in self._loaders]},
            )

        return self._loaders[source_enum]

    def list_supported_sources(self) -> list[str]:
        """Return list of all currently registered ETL source keys."""
        return [s.value for s in self._loaders]


@lru_cache(maxsize=1)
def get_loader_registry() -> LoaderRegistry:
    """Retrieve global singleton LoaderRegistry."""
    return LoaderRegistry()
