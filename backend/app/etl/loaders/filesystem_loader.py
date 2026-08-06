"""Production-Ready Local Filesystem ETL Loader for Investiga.

Provides asynchronous, recursive file discovery, robust filtering, symlink cycle protection,
deduplication, and streaming ingestion compatibility with StorageService.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from app.core.logging import get_logger
from app.etl.exceptions import (
    ETLDiscoveryException,
    ETLLoadException,
    ETLValidationException,
)
from app.etl.loaders.base_loader import BaseLoader
from app.etl.models import (
    ETLConfiguration,
    ETLDiscoveredItem,
    ETLDocumentStreamItem,
    ETLSource,
)

logger = get_logger(__name__)


class FilesystemLoader(BaseLoader):
    """Production filesystem data loader with recursive traversal and security controls."""

    SOURCE_TYPE: ClassVar[ETLSource] = ETLSource.FILESYSTEM

    def validate(self, config: ETLConfiguration) -> bool:
        """Validate that source path exists, is accessible, and adheres to security constraints."""
        super().validate(config)

        path_obj = Path(config.source_path_or_uri).resolve()
        if not path_obj.exists():
            raise ETLValidationException(
                message=f"Local path '{config.source_path_or_uri}' does not exist.",
                source=self.SOURCE_TYPE.value,
                details={"resolved_path": str(path_obj)},
            )

        if not os.access(path_obj, os.R_OK):
            raise ETLValidationException(
                message=f"Local path '{config.source_path_or_uri}' is not readable (permission denied).",
                source=self.SOURCE_TYPE.value,
                details={"resolved_path": str(path_obj)},
            )

        return True

    async def health_check(self) -> bool:
        """Verify local filesystem subsystem is operating normally."""
        try:
            return os.path.exists(os.getcwd())
        except Exception:
            return False

    async def discover(
        self,
        config: ETLConfiguration,
    ) -> AsyncIterator[ETLDiscoveredItem]:
        """Recursively scan filesystem path and yield matching discovered item metadata."""
        self.validate(config)

        root_path = Path(config.source_path_or_uri).resolve()
        visited_inodes: set[tuple[int, int]] = set()
        visited_realpaths: set[str] = set()

        discovered_count = 0

        # Run filesystem traversal asynchronously in worker thread
        def _traverse_sync() -> list[ETLDiscoveredItem]:
            items: list[ETLDiscoveredItem] = []

            # Single file target
            if root_path.is_file():
                stat = root_path.stat()
                rel_path = root_path.name
                ext = (
                    root_path.suffix.lower()
                    if root_path.name != "Dockerfile"
                    else ".dockerfile"
                )
                if self._matches_filters(rel_path, root_path.name, ext, config):
                    if stat.st_size <= config.max_file_size_bytes:
                        mod_time = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
                        items.append(
                            ETLDiscoveredItem(
                                source_uri=str(root_path),
                                relative_path=rel_path,
                                filename=root_path.name,
                                extension=ext,
                                size_bytes=stat.st_size,
                                modified_at=mod_time,
                                mime_type=self._resolve_mime(root_path.name, ext),
                                metadata={
                                    "absolute_path": str(root_path),
                                    "created_at": datetime.fromtimestamp(
                                        stat.st_ctime, tz=UTC
                                    ).isoformat(),
                                },
                            )
                        )
                return items

            # Directory traversal
            for root, dirs, files in os.walk(
                root_path,
                topdown=True,
                followlinks=config.follow_symlinks,
            ):
                # Filter hidden directories in-place if ignore_hidden is active
                if config.ignore_hidden:
                    dirs[:] = [
                        d
                        for d in dirs
                        if not d.startswith(".")
                        and d
                        not in {"node_modules", "__pycache__", "venv", ".git", ".svn"}
                    ]

                # If symlinks not followed, filter out symlinked directories
                if not config.follow_symlinks:
                    dirs[:] = [
                        d for d in dirs if not os.path.islink(os.path.join(root, d))
                    ]

                # Check directory loop / cycle prevention via inode
                try:
                    dir_stat = os.stat(root)
                    dir_key = (dir_stat.st_dev, dir_stat.st_ino)
                    if dir_key in visited_inodes:
                        logger.warning(
                            "filesystem_loader_cycle_detected", directory=root
                        )
                        dirs.clear()
                        continue
                    visited_inodes.add(dir_key)
                except OSError:
                    continue

                for fname in sorted(files):
                    file_path = Path(root) / fname

                    # Check symlink protection
                    if not config.follow_symlinks and file_path.is_symlink():
                        continue

                    # Canonical path deduplication
                    try:
                        real_p = str(file_path.resolve())
                    except OSError:
                        continue

                    if real_p in visited_realpaths:
                        continue
                    visited_realpaths.add(real_p)

                    # Compute relative path from root
                    try:
                        rel_path = str(file_path.relative_to(root_path)).replace(
                            "\\", "/"
                        )
                    except ValueError:
                        rel_path = fname

                    ext = file_path.suffix.lower()
                    if fname == "Dockerfile" or fname.startswith("Dockerfile."):
                        ext = ".dockerfile"

                    # Apply filtering rules
                    if not self._matches_filters(rel_path, fname, ext, config):
                        continue

                    # Read stat
                    try:
                        stat = file_path.stat()
                    except OSError as stat_err:
                        logger.warning(
                            "filesystem_loader_stat_failed",
                            path=str(file_path),
                            error=str(stat_err),
                        )
                        continue

                    # File size constraints
                    if stat.st_size > config.max_file_size_bytes:
                        logger.debug(
                            "filesystem_loader_file_exceeds_size",
                            path=str(file_path),
                            size=stat.st_size,
                            max_size=config.max_file_size_bytes,
                        )
                        continue

                    mod_time = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
                    items.append(
                        ETLDiscoveredItem(
                            source_uri=str(file_path),
                            relative_path=rel_path,
                            filename=fname,
                            extension=ext,
                            size_bytes=stat.st_size,
                            modified_at=mod_time,
                            mime_type=self._resolve_mime(fname, ext),
                            metadata={
                                "absolute_path": str(file_path),
                                "relative_path": rel_path,
                                "created_at": datetime.fromtimestamp(
                                    stat.st_ctime, tz=UTC
                                ).isoformat(),
                            },
                        )
                    )

                    if config.max_files is not None and len(items) >= config.max_files:
                        return items

            return items

        try:
            discovered_items = await asyncio.to_thread(_traverse_sync)
        except Exception as exc:
            raise ETLDiscoveryException(
                message=f"Failed to traverse filesystem at '{config.source_path_or_uri}': {exc}",
                source=self.SOURCE_TYPE.value,
                details={"error": str(exc)},
            ) from exc

        for item in discovered_items:
            discovered_count += 1
            yield item
            if config.max_files is not None and discovered_count >= config.max_files:
                break

    async def load(
        self,
        item: ETLDiscoveredItem,
        config: ETLConfiguration,
    ) -> ETLDocumentStreamItem:
        """Asynchronously read and return document binary stream."""
        file_path = Path(item.source_uri)

        def _read_file_sync() -> bytes:
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            return file_path.read_bytes()

        try:
            content_bytes = await asyncio.to_thread(_read_file_sync)
        except Exception as exc:
            raise ETLLoadException(
                message=f"Failed to read file from '{item.source_uri}': {exc}",
                source_uri=item.source_uri,
                source=self.SOURCE_TYPE.value,
                details={"error": str(exc)},
            ) from exc

        checksum = hashlib.sha256(content_bytes).hexdigest()

        mime = item.mime_type or self._resolve_mime(item.filename, item.extension)

        return ETLDocumentStreamItem(
            content=content_bytes,
            filename=item.filename,
            source_uri=item.source_uri,
            mime_type=mime,
            title=Path(item.filename).stem,
            category=config.category,
            size_bytes=len(content_bytes),
            checksum=checksum,
            metadata={
                **item.metadata,
                "relative_path": item.relative_path,
                "source_type": self.SOURCE_TYPE.value,
            },
        )

    def _resolve_mime(self, filename: str, extension: str) -> str:
        """Resolve MIME type using canonical storage mapping."""
        # Check standard FileValidator mapping
        known = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".txt": "text/plain",
            ".text": "text/plain",
            ".md": "text/markdown",
            ".markdown": "text/markdown",
            ".html": "text/html",
            ".htm": "text/html",
            ".py": "text/x-python",
            ".js": "text/javascript",
            ".ts": "text/typescript",
            ".tsx": "text/tsx",
            ".jsx": "text/jsx",
            ".java": "text/x-java-source",
            ".c": "text/x-c",
            ".cpp": "text/x-c++",
            ".cs": "text/x-csharp",
            ".go": "text/x-go",
            ".rs": "text/x-rust",
            ".kt": "text/x-kotlin",
            ".swift": "text/x-swift",
            ".php": "text/x-php",
            ".sql": "text/x-sql",
            ".sh": "text/x-sh",
            ".ps1": "text/x-powershell",
            ".dockerfile": "text/x-dockerfile",
        }
        if extension in known:
            return known[extension]
        if filename.lower() == "dockerfile" or filename.lower().startswith(
            "dockerfile."
        ):
            return "text/x-dockerfile"
        return "application/octet-stream"
