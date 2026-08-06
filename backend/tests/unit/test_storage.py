"""Unit Tests for Storage Subsystem and Security Validators.

Covers:
- FileValidator security validations (path traversal, executables, double extensions, empty files, size constraints)
- LocalStorageProvider async I/O, automatic directory creation, path isolation, and deletion
- StorageService end-to-end file persistence, UUID generation, cryptographic checksums, and metadata extraction
"""

import tempfile
import uuid
from pathlib import Path

import pytest

from app.core.config import Settings
from app.storage.exceptions import (
    FileTooLargeException,
    InvalidFileException,
    StorageFileNotFoundException,
    UnsupportedFileTypeException,
)
from app.storage.local_storage import LocalStorageProvider
from app.storage.storage_service import StorageService
from app.storage.validators import FileValidator

# ------------------------------------------------------------------------------
# 1. FileValidator Tests
# ------------------------------------------------------------------------------


def test_validator_sanitize_and_validate_filename_valid() -> None:
    """Test valid filenames with standard supported extensions."""
    name, ext = FileValidator.sanitize_and_validate_filename("incident_report_2026.pdf")
    assert name == "incident_report_2026.pdf"
    assert ext == ".pdf"

    name, ext = FileValidator.sanitize_and_validate_filename(
        "system-config.YAML", allowed_extensions=[".yaml", ".yml"]
    )
    assert name == "system-config.YAML"
    assert ext == ".yaml"


def test_validator_reject_empty_or_whitespace_filename() -> None:
    """Test rejection of empty or whitespace-only filenames."""
    with pytest.raises(InvalidFileException):
        FileValidator.sanitize_and_validate_filename("")

    with pytest.raises(InvalidFileException):
        FileValidator.sanitize_and_validate_filename("    ")


def test_validator_reject_path_traversal_attacks() -> None:
    """Test rejection of directory traversal sequences."""
    traversal_payloads = [
        "../../etc/passwd",
        "..\\..\\windows\\system32\\cmd.exe",
        "folder/subfolder/file.pdf",
        "c:\\boot.ini",
        "....//....//file.pdf",
    ]
    for payload in traversal_payloads:
        with pytest.raises(InvalidFileException):
            FileValidator.sanitize_and_validate_filename(payload)


def test_validator_reject_null_bytes_and_control_chars() -> None:
    """Test rejection of null bytes and non-printable control characters."""
    with pytest.raises(InvalidFileException):
        FileValidator.sanitize_and_validate_filename("document\0.pdf")

    with pytest.raises(InvalidFileException):
        FileValidator.sanitize_and_validate_filename("doc\x07bell.pdf")


def test_validator_reject_hidden_and_reserved_names() -> None:
    """Test rejection of dotfiles and Windows reserved system device names."""
    with pytest.raises(InvalidFileException):
        FileValidator.sanitize_and_validate_filename(".hidden_secret.pdf")

    for reserved in ["CON.pdf", "aux.txt", "prn.log", "NUL.docx", "com1.pdf"]:
        with pytest.raises(InvalidFileException):
            FileValidator.sanitize_and_validate_filename(reserved)


def test_validator_reject_executables_and_double_extensions() -> None:
    """Test strict rejection of binary executables and disguised double extensions."""
    executable_files = [
        "malware.exe",
        "payload.bat",
        "command.cmd",
        "macro.vbs",
        "library.dll",
        "trojan.com",
        "installer.msi",
        "driver.sys",
    ]
    for filename in executable_files:
        with pytest.raises((UnsupportedFileTypeException, InvalidFileException)):
            FileValidator.sanitize_and_validate_filename(filename)

    double_extension_files = [
        "report.pdf.exe",
        "safe_document.exe.pdf",
        "image.bat.pdf",
        "guide.exe.docx",
    ]
    for filename in double_extension_files:
        with pytest.raises((InvalidFileException, UnsupportedFileTypeException)):
            FileValidator.sanitize_and_validate_filename(filename)


def test_validator_accepts_source_code_and_html_files() -> None:
    """Test validation and MIME resolution for supported HTML and source code files."""
    valid_files = [
        ("index.html", ".html", "text/html"),
        ("app.py", ".py", "text/x-python"),
        ("index.ts", ".ts", "text/typescript"),
        ("component.tsx", ".tsx", "text/tsx"),
        ("main.rs", ".rs", "text/x-rust"),
        ("server.go", ".go", "text/x-go"),
        ("Dockerfile", ".dockerfile", "text/x-dockerfile"),
    ]
    for filename, expected_ext, expected_mime in valid_files:
        name, ext = FileValidator.sanitize_and_validate_filename(filename)
        assert ext == expected_ext
        mime = FileValidator.detect_and_validate_mime_type(
            content=b"sample content",
            filename=name,
            extension=ext,
        )
        assert mime == expected_mime


def test_validator_reject_disallowed_extensions() -> None:
    """Test enforcement of allowed extensions whitelist."""
    with pytest.raises(UnsupportedFileTypeException):
        FileValidator.sanitize_and_validate_filename(
            "archive.zip",
            allowed_extensions=[".pdf", ".docx", ".txt"],
        )


def test_validator_file_size() -> None:
    """Test file size validation (empty file and oversized file)."""
    # Reject 0 bytes
    with pytest.raises(InvalidFileException):
        FileValidator.validate_file_size(0, max_size_mb=10)

    # Valid size
    FileValidator.validate_file_size(5 * 1024 * 1024, max_size_mb=10)

    # Reject exceeding limit
    with pytest.raises(FileTooLargeException):
        FileValidator.validate_file_size(15 * 1024 * 1024, max_size_mb=10)


def test_validator_detect_and_validate_mime_type() -> None:
    """Test MIME type detection and magic byte verification."""
    pdf_content = b"%PDF-1.7 valid pdf header content"
    mime = FileValidator.detect_and_validate_mime_type(
        content=pdf_content,
        filename="report.pdf",
        extension=".pdf",
        allowed_mime_types=["application/pdf"],
    )
    assert mime == "application/pdf"

    # Reject fake PDF with text content
    with pytest.raises(UnsupportedFileTypeException):
        FileValidator.detect_and_validate_mime_type(
            content=b"This is not a pdf file",
            filename="fake.pdf",
            extension=".pdf",
            allowed_mime_types=["application/pdf"],
        )


# ------------------------------------------------------------------------------
# 2. LocalStorageProvider Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_local_storage_provider_crud() -> None:
    """Test local storage save, read, exists, and delete operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        provider = LocalStorageProvider(base_directory=temp_dir)
        content = b"Knowledge base document binary test content"
        stored_name = f"{uuid.uuid4().hex}.txt"

        # 1. Save
        path = await provider.save(content=content, stored_filename=stored_name)
        assert Path(path).exists()
        assert Path(path).is_file()

        # 2. Exists
        assert await provider.exists(stored_name) is True
        assert await provider.exists("non_existent_file.txt") is False

        # 3. Read
        read_bytes = await provider.read(stored_name)
        assert read_bytes == content

        # 4. Delete
        assert await provider.delete(stored_name) is True
        assert await provider.exists(stored_name) is False
        assert await provider.delete(stored_name) is False

        # 5. Read non-existent raises StorageFileNotFoundException
        with pytest.raises(StorageFileNotFoundException):
            await provider.read(stored_name)


@pytest.mark.asyncio
async def test_local_storage_provider_path_traversal_guard() -> None:
    """Test prevention of path traversal in storage identifiers."""
    with tempfile.TemporaryDirectory() as temp_dir:
        provider = LocalStorageProvider(base_directory=temp_dir)

        with pytest.raises(InvalidFileException):
            await provider.save(b"test", "../../escape.txt")

        with pytest.raises(InvalidFileException):
            await provider.read("../secret.txt")


# ------------------------------------------------------------------------------
# 3. StorageService Orchestration Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_storage_service_store_file_end_to_end() -> None:
    """Test StorageService end-to-end store, checksum calculation, and metadata generation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        settings = Settings()
        settings.storage.upload_directory = temp_dir
        settings.storage.max_upload_size_mb = 10

        provider = LocalStorageProvider(base_directory=temp_dir)
        service = StorageService(provider=provider, settings=settings)

        pdf_payload = b"%PDF-1.4 Enterprise Architecture Document"
        metadata = await service.store_file(
            filename="architecture_v1.pdf",
            content=pdf_payload,
            client_mime_type="application/pdf",
        )

        assert metadata.original_filename == "architecture_v1.pdf"
        assert metadata.file_extension == ".pdf"
        assert metadata.mime_type == "application/pdf"
        assert metadata.file_size == len(pdf_payload)
        assert len(metadata.checksum) == 64
        assert metadata.stored_filename.endswith(".pdf")
        assert await service.exists(metadata.stored_filename) is True

        # Read back content
        fetched_content = await service.read_file(metadata.stored_filename)
        assert fetched_content == pdf_payload

        # Clean up
        deleted = await service.delete_file(metadata.stored_filename)
        assert deleted is True
        assert await service.exists(metadata.stored_filename) is False
