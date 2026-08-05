"""Storage Orchestration Service for Investiga.

This module provides high-level file persistence workflows, including filename
sanitization, UUID storage name generation, SHA-256 checksum calculation,
MIME verification, and physical deletion management.
"""

import hashlib
import uuid
from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.storage.local_storage import LocalStorageProvider, StorageProvider
from app.storage.validators import FileValidator

logger = get_logger(__name__)


@dataclass(frozen=True)
class StoredFileMetadata:
    """Immutable data record containing physical file attributes and cryptographic digests."""

    original_filename: str
    stored_filename: str
    file_extension: str
    mime_type: str
    file_size: int
    checksum: str
    storage_path: str


class StorageService:
    """High-level application service orchestrating file storage and integrity verification."""

    def __init__(
        self,
        provider: StorageProvider | None = None,
        settings: Settings | None = None,
        validator: FileValidator | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._validator = validator or FileValidator()
        self._provider = provider or LocalStorageProvider(
            base_directory=self._settings.storage.upload_directory
        )

    @property
    def provider(self) -> StorageProvider:
        """Access the underlying storage provider."""
        return self._provider

    async def store_file(
        self,
        filename: str,
        content: bytes,
        client_mime_type: str | None = None,
    ) -> StoredFileMetadata:
        """Validate, fingerprint, and persist an uploaded file payload.

        Workflow:
            1. Sanitize filename and validate against path traversal & forbidden extensions.
            2. Validate file size against configured limit.
            3. Detect canonical MIME type and verify magic bytes.
            4. Compute SHA-256 cryptographic digest.
            5. Generate collision-resistant UUID storage filename.
            6. Persist file content via the active storage provider.
            7. Return structured metadata object.

        Args:
            filename: Client-supplied raw filename string.
            content: Raw file byte array.
            client_mime_type: Optional HTTP Content-Type reported by client.

        Returns:
            StoredFileMetadata: Complete verified metadata description.
        """
        # 1. Validate filename and extension
        sanitized_filename, extension = self._validator.sanitize_and_validate_filename(
            filename=filename,
            allowed_extensions=self._settings.storage.allowed_extensions,
        )

        # 2. Validate file size
        file_size = len(content)
        self._validator.validate_file_size(
            size_bytes=file_size,
            max_size_mb=self._settings.storage.max_upload_size_mb,
        )

        # 3. Detect and validate MIME type
        mime_type = self._validator.detect_and_validate_mime_type(
            content=content,
            filename=sanitized_filename,
            extension=extension,
            client_mime_type=client_mime_type,
            allowed_mime_types=self._settings.storage.allowed_mime_types,
        )

        # 4. Calculate SHA-256 checksum
        checksum = hashlib.sha256(content).hexdigest()

        # 5. Generate secure UUID stored filename
        stored_filename = f"{uuid.uuid4().hex}{extension}"

        # 6. Save via storage provider
        storage_path = await self._provider.save(
            content=content,
            stored_filename=stored_filename,
        )

        logger.info(
            "file_stored_successfully",
            original_filename=sanitized_filename,
            stored_filename=stored_filename,
            file_size=file_size,
            mime_type=mime_type,
            checksum=checksum,
        )

        return StoredFileMetadata(
            original_filename=sanitized_filename,
            stored_filename=stored_filename,
            file_extension=extension,
            mime_type=mime_type,
            file_size=file_size,
            checksum=checksum,
            storage_path=storage_path,
        )

    async def delete_file(self, stored_filename: str) -> bool:
        """Remove a physical file from storage.

        Args:
            stored_filename: The unique identifier name on disk.

        Returns:
            bool: True if deleted, False if file did not exist.
        """
        deleted = await self._provider.delete(stored_filename)
        if deleted:
            logger.info("file_deleted_from_storage", stored_filename=stored_filename)
        return deleted

    async def exists(self, stored_filename: str) -> bool:
        """Verify whether a file exists in the storage provider."""
        return await self._provider.exists(stored_filename)

    async def read_file(self, stored_filename: str) -> bytes:
        """Read and return content of a stored file."""
        return await self._provider.read(stored_filename)
