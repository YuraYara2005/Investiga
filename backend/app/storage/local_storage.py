"""Storage Provider Interface and Local Filesystem Implementation.

This module provides the abstract `StorageProvider` contract and the production-ready
`LocalStorageProvider` implementation, enforcing asynchronous file I/O and strict
path isolation.
"""

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.logging import get_logger
from app.storage.exceptions import (
    InvalidFileException,
    StorageException,
    StorageFileNotFoundException,
)

logger = get_logger(__name__)


class StorageProvider(ABC):
    """Abstract interface defining the contract for physical/object storage providers."""

    @abstractmethod
    async def save(self, content: bytes, stored_filename: str) -> str:
        """Persist raw byte content to storage.

        Args:
            content: File bytes.
            stored_filename: Secure storage identifier (e.g., UUID-based name).

        Returns:
            str: Resolved storage path or URI.
        """
        pass

    @abstractmethod
    async def read(self, stored_filename: str) -> bytes:
        """Read and return byte content of a stored file.

        Args:
            stored_filename: Storage identifier.

        Returns:
            bytes: Raw file content.
        """
        pass

    @abstractmethod
    async def delete(self, stored_filename: str) -> bool:
        """Remove a stored file from persistence.

        Args:
            stored_filename: Storage identifier.

        Returns:
            bool: True if deleted, False if file was not found.
        """
        pass

    @abstractmethod
    async def exists(self, stored_filename: str) -> bool:
        """Verify whether a file exists in the storage provider.

        Args:
            stored_filename: Storage identifier.

        Returns:
            bool: True if file exists, False otherwise.
        """
        pass

    @abstractmethod
    def get_full_path(self, stored_filename: str) -> str:
        """Retrieve the absolute URI or filesystem path for a stored identifier."""
        pass


class LocalStorageProvider(StorageProvider):
    """Local filesystem storage provider with automatic directory creation and path isolation."""

    def __init__(self, base_directory: str | Path) -> None:
        self._base_path = Path(base_directory).resolve()
        # Automatically ensure base upload directory exists
        self._base_path.mkdir(parents=True, exist_ok=True)

    @property
    def base_path(self) -> Path:
        """Absolute root directory for file storage."""
        return self._base_path

    def _resolve_safe_path(self, stored_filename: str) -> Path:
        """Resolve absolute path while guaranteeing no directory escape."""
        if (
            not stored_filename
            or "/" in stored_filename
            or "\\" in stored_filename
            or ".." in stored_filename
        ):
            raise InvalidFileException(
                message="Invalid stored filename. Path separators are not allowed.",
                details={"stored_filename": stored_filename},
            )

        target_path = (self._base_path / stored_filename).resolve()
        # Ensure the resolved target resides strictly inside the base directory
        if not str(target_path).startswith(str(self._base_path)):
            raise InvalidFileException(
                message="Directory traversal attack detected in storage identifier.",
                details={"stored_filename": stored_filename},
            )

        return target_path

    async def save(self, content: bytes, stored_filename: str) -> str:
        """Persist file bytes to local filesystem asynchronously."""
        target_path = self._resolve_safe_path(stored_filename)

        def _sync_write() -> str:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "wb") as f:
                f.write(content)
            return str(target_path)

        try:
            return await asyncio.to_thread(_sync_write)
        except Exception as exc:
            logger.error(
                "local_storage_write_failed",
                filename=stored_filename,
                path=str(target_path),
                error=str(exc),
                exc_info=True,
            )
            raise StorageException(
                message=f"Failed to write file to local disk: {exc}",
                details={"stored_filename": stored_filename},
            ) from exc

    async def read(self, stored_filename: str) -> bytes:
        """Read file bytes from local filesystem asynchronously."""
        target_path = self._resolve_safe_path(stored_filename)

        def _sync_read() -> bytes:
            if not target_path.exists() or not target_path.is_file():
                raise StorageFileNotFoundException(
                    message=f"File '{stored_filename}' was not found on local disk.",
                    details={"path": str(target_path)},
                )
            with open(target_path, "rb") as f:
                return f.read()

        try:
            return await asyncio.to_thread(_sync_read)
        except StorageFileNotFoundException:
            raise
        except Exception as exc:
            logger.error(
                "local_storage_read_failed",
                filename=stored_filename,
                error=str(exc),
                exc_info=True,
            )
            raise StorageException(
                message=f"Failed to read file from disk: {exc}",
                details={"stored_filename": stored_filename},
            ) from exc

    async def delete(self, stored_filename: str) -> bool:
        """Remove file from local filesystem asynchronously."""
        target_path = self._resolve_safe_path(stored_filename)

        def _sync_delete() -> bool:
            if target_path.exists() and target_path.is_file():
                try:
                    target_path.unlink()
                    return True
                except Exception as exc:
                    logger.error(
                        "local_storage_unlink_failed",
                        filename=stored_filename,
                        error=str(exc),
                    )
                    return False
            return False

        return await asyncio.to_thread(_sync_delete)

    async def exists(self, stored_filename: str) -> bool:
        """Check whether file exists on disk."""
        target_path = self._resolve_safe_path(stored_filename)

        def _sync_exists() -> bool:
            return target_path.exists() and target_path.is_file()

        return await asyncio.to_thread(_sync_exists)

    def get_full_path(self, stored_filename: str) -> str:
        """Return absolute filesystem path."""
        target_path = self._resolve_safe_path(stored_filename)
        return str(target_path)
