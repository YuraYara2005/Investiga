"""File Security and Integrity Validators for Investiga.

This module provides strict validation routines defending against path traversal,
malicious double extensions, prohibited executable formats, spoofed MIME types,
and oversized payloads.
"""

import mimetypes
import re
from pathlib import PurePath
from typing import ClassVar

from app.storage.exceptions import (
    FileTooLargeException,
    InvalidFileException,
    UnsupportedFileTypeException,
)

# Known dangerous executable and script extensions strictly prohibited
DISALLOWED_EXECUTABLE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".exe",
        ".bat",
        ".cmd",
        ".sh",
        ".bash",
        ".ps1",
        ".psm1",
        ".vbs",
        ".vbe",
        ".js",
        ".jse",
        ".wsf",
        ".wsh",
        ".msi",
        ".msp",
        ".com",
        ".scr",
        ".hta",
        ".cpl",
        ".jar",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".elf",
        ".py",
        ".pyc",
        ".pyd",
        ".php",
        ".asp",
        ".aspx",
        ".jsp",
        ".cgi",
        ".pl",
    }
)

# Reserved device filenames in Windows / POSIX that can cause denial of service
RESERVED_SYSTEM_NAMES: frozenset[str] = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        "com1",
        "com2",
        "com3",
        "com4",
        "com5",
        "com6",
        "com7",
        "com8",
        "com9",
        "lpt1",
        "lpt2",
        "lpt3",
        "lpt4",
        "lpt5",
        "lpt6",
        "lpt7",
        "lpt8",
        "lpt9",
    }
)


class FileValidator:
    """Validator providing security assertions and type verification for uploaded files."""

    MAGIC_SIGNATURES: ClassVar[dict[str, list[bytes]]] = {
        ".pdf": [b"%PDF-"],
        ".docx": [b"PK\x03\x04"],  # ZIP container header
        ".json": [b"{", b"[", b" "],
        ".yaml": [b"---", b"%YAML"],
        ".yml": [b"---", b"%YAML"],
    }

    @staticmethod
    def sanitize_and_validate_filename(
        filename: str,
        allowed_extensions: list[str] | None = None,
    ) -> tuple[str, str]:
        """Validate filename against security exploits and return sanitized name and extension.

        Args:
            filename: Raw client-supplied filename string.
            allowed_extensions: Optional list of permitted lowercase extensions (e.g. ['.pdf', '.docx']).

        Returns:
            tuple[str, str]: (sanitized_base_filename, normalized_extension)

        Raises:
            InvalidFileException: If filename is empty, contains path traversal, double extension,
                                  control characters, or prohibited names.
            UnsupportedFileTypeException: If extension is not permitted.
        """
        if not filename or not filename.strip():
            raise InvalidFileException(
                message="Filename cannot be empty or whitespace.",
                details={"filename": filename},
            )

        raw_name = filename.strip()

        # 1. Null-byte injection check
        if "\0" in raw_name or "\x00" in raw_name:
            raise InvalidFileException(
                message="Filename contains illegal null bytes.",
                details={"filename": raw_name},
            )

        # 2. Path traversal attack checks
        if ".." in raw_name or "/" in raw_name or "\\" in raw_name:
            raise InvalidFileException(
                message="Path traversal characters ('..', '/', '\\') are strictly prohibited in filenames.",
                details={"filename": raw_name},
            )

        # Extract only the base name (strip any leading directory prefixes if somehow present)
        pure_name = PurePath(raw_name).name
        if not pure_name or pure_name.startswith("."):
            raise InvalidFileException(
                message="Hidden files or dotfiles are not permitted for upload.",
                details={"filename": raw_name},
            )

        # 3. Reserved Windows/POSIX name check
        stem = pure_name.split(".")[0].lower()
        if stem in RESERVED_SYSTEM_NAMES:
            raise InvalidFileException(
                message=f"Filename '{pure_name}' uses a reserved system device name.",
                details={"filename": pure_name},
            )

        # 4. Prohibit control characters or non-printable ASCII
        if re.search(r"[\x00-\x1f\x7f]", pure_name):
            raise InvalidFileException(
                message="Filename contains non-printable control characters.",
                details={"filename": pure_name},
            )

        # 5. Check double extensions and disguises (e.g., 'document.pdf.exe' or 'exploit.exe.pdf')
        parts = pure_name.split(".")
        if len(parts) < 2:
            raise InvalidFileException(
                message="File must possess a valid file extension.",
                details={"filename": pure_name},
            )

        # Disallow multiple extensions if any preceding part is an executable extension
        for part in parts[1:-1]:
            preceding_ext = f".{part.lower()}"
            if preceding_ext in DISALLOWED_EXECUTABLE_EXTENSIONS:
                raise InvalidFileException(
                    message=f"Double extension attack detected with prohibited token '{preceding_ext}'.",
                    details={
                        "filename": pure_name,
                        "prohibited_extension": preceding_ext,
                    },
                )

        # 6. Extract normalized extension
        ext = f".{parts[-1].lower()}"

        # 7. Check strictly disallowed executable extensions
        if ext in DISALLOWED_EXECUTABLE_EXTENSIONS:
            raise UnsupportedFileTypeException(
                message=f"Executable and script file extension '{ext}' is strictly prohibited.",
                details={"extension": ext, "filename": pure_name},
            )

        # 8. Check allowed extensions list if provided
        if allowed_extensions is not None:
            normalized_allowed = [
                e.lower() if e.startswith(".") else f".{e.lower()}"
                for e in allowed_extensions
            ]
            if ext not in normalized_allowed:
                raise UnsupportedFileTypeException(
                    message=f"File extension '{ext}' is not in the list of allowed extensions: {normalized_allowed}.",
                    details={
                        "extension": ext,
                        "allowed_extensions": normalized_allowed,
                    },
                )

        return pure_name, ext

    @staticmethod
    def validate_file_size(size_bytes: int, max_size_mb: int) -> None:
        """Enforce byte size boundary constraints.

        Args:
            size_bytes: Actual size in bytes.
            max_size_mb: Configured maximum threshold in megabytes.

        Raises:
            InvalidFileException: If file is empty (0 bytes) or negative.
            FileTooLargeException: If size exceeds the maximum permitted MB.
        """
        if size_bytes <= 0:
            raise InvalidFileException(
                message="Uploaded file is empty (0 bytes).",
                details={"size_bytes": size_bytes},
            )

        max_allowed_bytes = max_size_mb * 1024 * 1024
        if size_bytes > max_allowed_bytes:
            raise FileTooLargeException(
                size_bytes=size_bytes,
                max_size_mb=max_size_mb,
            )

    @classmethod
    def detect_and_validate_mime_type(
        cls,
        content: bytes,
        filename: str,
        extension: str,
        client_mime_type: str | None = None,
        allowed_mime_types: list[str] | None = None,
    ) -> str:
        """Determine canonical MIME type using extension, signature, and validate against allowed list.

        Args:
            content: Raw byte payload.
            filename: Normalized filename.
            extension: Normalized extension (e.g. '.pdf').
            client_mime_type: MIME type reported in HTTP header (untrusted).
            allowed_mime_types: Optional list of permitted MIME types.

        Returns:
            str: Verified canonical MIME type string.

        Raises:
            UnsupportedFileTypeException: If MIME type is disallowed or violates magic byte assertions.
        """
        # Determine canonical MIME type from extension
        guessed_type, _ = mimetypes.guess_type(filename)
        canonical_mime = guessed_type

        # Fallback mappings for common modern formats
        if not canonical_mime:
            if extension in {".yaml", ".yml"}:
                canonical_mime = "application/x-yaml"
            elif extension == ".md":
                canonical_mime = "text/markdown"
            elif extension == ".log":
                canonical_mime = "text/plain"
            elif client_mime_type:
                canonical_mime = client_mime_type
            else:
                canonical_mime = "application/octet-stream"

        # Verify magic header if signature is defined
        if extension in cls.MAGIC_SIGNATURES:
            signatures = cls.MAGIC_SIGNATURES[extension]
            if extension in {".json", ".yaml", ".yml"}:
                # For text-based formats, check if readable ASCII/UTF-8
                try:
                    content[:1024].decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise UnsupportedFileTypeException(
                        message=f"File with extension '{extension}' contains invalid binary data instead of valid text.",
                        details={"extension": extension, "filename": filename},
                    ) from exc
            else:
                # For binary formats, check magic header bytes
                matches = any(content.startswith(sig) for sig in signatures)
                if not matches:
                    raise UnsupportedFileTypeException(
                        message=f"File header magic bytes do not match expected signature for '{extension}'.",
                        details={"extension": extension, "filename": filename},
                    )

        # Validate against allowed MIME types if configured
        if allowed_mime_types is not None:
            normalized_allowed = [m.lower() for m in allowed_mime_types]
            # Also allow text/plain or text/x-log for log/md/txt
            if canonical_mime.lower() not in normalized_allowed:
                # Check client MIME type as a fallback alternative if permitted
                if client_mime_type and client_mime_type.lower() in normalized_allowed:
                    canonical_mime = client_mime_type.lower()
                else:
                    raise UnsupportedFileTypeException(
                        message=f"MIME type '{canonical_mime}' is not permitted for ingestion.",
                        details={
                            "mime_type": canonical_mime,
                            "allowed_mime_types": normalized_allowed,
                        },
                    )

        return canonical_mime
