"""Unit Tests for Enterprise ETL Subsystem.

Validates FilesystemLoader discovery and filtering, ETLPipeline batch execution,
resumable checkpoints, job cancellation, scheduler mechanics, and placeholder loaders.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.etl import (
    APILoader,
    BaseLoader,
    ConfluenceLoader,
    ETLConfiguration,
    ETLDiscoveredItem,
    ETLJob,
    ETLJobStatus,
    ETLPipeline,
    ETLScheduler,
    ETLService,
    ETLSource,
    ETLStatistics,
    ETLValidationException,
    FilesystemLoader,
    GDriveLoader,
    GitHubLoader,
    LoaderRegistry,
    NotionLoader,
    ScheduleFrequency,
    SharePointLoader,
    WebsiteLoader,
)
from app.ingestion.models import IngestionMetrics, IngestionReport, IngestionStatus


@pytest.fixture
def sample_etl_dir(tmp_path: Path) -> Path:
    """Create a structured directory fixture with diverse documents for ETL testing."""
    root = tmp_path / "etl_source"
    root.mkdir()

    # Regular files
    (root / "README.md").write_text(
        "# Documentation\nWelcome to Investiga ETL.", encoding="utf-8"
    )
    (root / "app.py").write_text(
        "def main():\n    print('Hello ETL')\n", encoding="utf-8"
    )
    (root / "index.html").write_text(
        "<html><body><h1>ETL Web</h1></body></html>", encoding="utf-8"
    )
    (root / "Dockerfile").write_text(
        "FROM python:3.11\nWORKDIR /app\n", encoding="utf-8"
    )

    # Subdirectory with nested files
    docs_dir = root / "docs"
    docs_dir.mkdir()
    (docs_dir / "architecture.txt").write_text(
        "ETL Architecture Overview", encoding="utf-8"
    )
    (docs_dir / "api_spec.json").write_text(
        '{"title": "Investiga API"}', encoding="utf-8"
    )

    # Hidden folder & files (should be ignored by default)
    hidden_dir = root / ".git"
    hidden_dir.mkdir()
    (hidden_dir / "config").write_text("git config dummy", encoding="utf-8")
    (root / ".DS_Store").write_text("macOS meta", encoding="utf-8")

    # Ignored directory (e.g. node_modules)
    node_dir = root / "node_modules"
    node_dir.mkdir()
    (node_dir / "package.json").write_text("{}", encoding="utf-8")

    return root


# =============================================================================
# 1. FilesystemLoader Discovery and Traversal Tests
# =============================================================================


@pytest.mark.asyncio
async def test_filesystem_loader_recursive_discovery(sample_etl_dir: Path) -> None:
    """Test recursive discovery ignoring hidden files and node_modules by default."""
    loader = FilesystemLoader()
    config = ETLConfiguration(
        source_type=ETLSource.FILESYSTEM,
        source_path_or_uri=str(sample_etl_dir),
        recursive=True,
        ignore_hidden=True,
    )

    discovered: list[ETLDiscoveredItem] = []
    async for item in loader.discover(config):
        discovered.append(item)

    filenames = {item.filename for item in discovered}
    assert "README.md" in filenames
    assert "app.py" in filenames
    assert "index.html" in filenames
    assert "Dockerfile" in filenames
    assert "architecture.txt" in filenames
    assert "api_spec.json" in filenames

    # Verify hidden files and node_modules were filtered out
    assert ".DS_Store" not in filenames
    assert "config" not in filenames
    assert not any(".git" in item.relative_path for item in discovered)
    assert not any("node_modules" in item.relative_path for item in discovered)


@pytest.mark.asyncio
async def test_filesystem_loader_filtering_and_max_files(sample_etl_dir: Path) -> None:
    """Test include/exclude pattern matching and max_files limits."""
    loader = FilesystemLoader()

    # Filter to only .py and .md files
    config_ext = ETLConfiguration(
        source_type=ETLSource.FILESYSTEM,
        source_path_or_uri=str(sample_etl_dir),
        allowed_extensions=[".py", ".md"],
    )
    discovered_ext = [item async for item in loader.discover(config_ext)]
    assert len(discovered_ext) == 2
    assert {item.filename for item in discovered_ext} == {"README.md", "app.py"}

    # Include pattern matching
    config_pattern = ETLConfiguration(
        source_type=ETLSource.FILESYSTEM,
        source_path_or_uri=str(sample_etl_dir),
        include_patterns=["*.html", "docs/*"],
    )
    discovered_pattern = [item async for item in loader.discover(config_pattern)]
    pattern_files = {item.filename for item in discovered_pattern}
    assert "index.html" in pattern_files
    assert "architecture.txt" in pattern_files

    # Exclude pattern
    config_exclude = ETLConfiguration(
        source_type=ETLSource.FILESYSTEM,
        source_path_or_uri=str(sample_etl_dir),
        exclude_patterns=["*.html", "*.json"],
    )
    discovered_exclude = [item async for item in loader.discover(config_exclude)]
    assert not any(item.filename.endswith(".html") for item in discovered_exclude)
    assert not any(item.filename.endswith(".json") for item in discovered_exclude)

    # Max files limit
    config_max = ETLConfiguration(
        source_type=ETLSource.FILESYSTEM,
        source_path_or_uri=str(sample_etl_dir),
        max_files=2,
    )
    discovered_max = [item async for item in loader.discover(config_max)]
    assert len(discovered_max) == 2


@pytest.mark.asyncio
async def test_filesystem_loader_load_item(sample_etl_dir: Path) -> None:
    """Test loading and materializing a discovered file payload into a stream item."""
    loader = FilesystemLoader()
    config = ETLConfiguration(
        source_type=ETLSource.FILESYSTEM,
        source_path_or_uri=str(sample_etl_dir),
        category="Engineering",
    )

    discovered_item = ETLDiscoveredItem(
        source_uri=str(sample_etl_dir / "app.py"),
        relative_path="app.py",
        filename="app.py",
        extension=".py",
        size_bytes=len((sample_etl_dir / "app.py").read_bytes()),
    )

    stream_item = await loader.load(discovered_item, config)
    assert stream_item.filename == "app.py"
    assert stream_item.category == "Engineering"
    assert b"Hello ETL" in stream_item.content
    assert stream_item.checksum is not None
    assert stream_item.mime_type == "text/x-python"


@pytest.mark.asyncio
async def test_filesystem_loader_validation_and_health_check() -> None:
    """Test validation errors for invalid paths and health check."""
    loader = FilesystemLoader()

    # Empty path validation
    with pytest.raises(ETLValidationException):
        loader.validate(ETLConfiguration(source_path_or_uri=""))

    # Non-existent path validation
    with pytest.raises(ETLValidationException):
        loader.validate(
            ETLConfiguration(source_path_or_uri="/invalid/non_existent_path_xyz")
        )

    # Health check
    assert await loader.health_check() is True


# =============================================================================
# 2. Placeholder Loaders Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "loader_cls,source_enum",
    [
        (GitHubLoader, ETLSource.GITHUB),
        (WebsiteLoader, ETLSource.WEBSITE),
        (APILoader, ETLSource.API),
        (SharePointLoader, ETLSource.SHAREPOINT),
        (GDriveLoader, ETLSource.GDRIVE),
        (NotionLoader, ETLSource.NOTION),
        (ConfluenceLoader, ETLSource.CONFLUENCE),
    ],
)
async def test_placeholder_loaders_conformity_and_not_implemented(
    loader_cls: type[BaseLoader],
    source_enum: ETLSource,
) -> None:
    """Verify all placeholder loaders inherit from BaseLoader, support their source, and raise NotImplementedError."""
    loader = loader_cls()
    assert loader.supports(source_enum) is True
    assert loader.supports("other_source") is False
    assert await loader.health_check() is True

    config = ETLConfiguration(
        source_type=source_enum,
        source_path_or_uri="https://example.com/source",
    )

    with pytest.raises(NotImplementedError):
        async for _ in loader.discover(config):
            pass

    dummy_item = ETLDiscoveredItem(
        source_uri="https://example.com/source/item1",
        relative_path="item1",
        filename="item1.txt",
        extension=".txt",
    )
    with pytest.raises(NotImplementedError):
        await loader.load(dummy_item, config)


# =============================================================================
# 3. Registry Tests
# =============================================================================


def test_loader_registry_lookup_and_custom_registration() -> None:
    """Test loader registry lookup, listing, and dynamic registration."""
    registry = LoaderRegistry()

    # Verify default registered loaders
    fs_loader = registry.get(ETLSource.FILESYSTEM)
    assert isinstance(fs_loader, FilesystemLoader)

    gh_loader = registry.get("github")
    assert isinstance(gh_loader, GitHubLoader)

    # Custom loader registration
    class CustomFilesystemLoader(FilesystemLoader):
        pass

    custom_instance = CustomFilesystemLoader()
    registry.register(ETLSource.FILESYSTEM, custom_instance)
    assert registry.get(ETLSource.FILESYSTEM) is custom_instance

    # Supported sources list
    sources = registry.list_supported_sources()
    assert "filesystem" in sources
    assert "confluence" in sources


# =============================================================================
# 4. Pipeline Orchestration, Progress Tracking & Resilience Tests
# =============================================================================


@pytest.mark.asyncio
async def test_etl_pipeline_successful_execution(sample_etl_dir: Path) -> None:
    """Test full ETL pipeline execution coordinating loader discovery, ingestion, and telemetry."""
    user_id = uuid.uuid4()
    mock_session = AsyncMock()

    # Mock DocumentIngestionPipeline
    mock_ingestion_pipeline = MagicMock()
    mock_ingestion_pipeline.ingest_content = AsyncMock()

    def _create_mock_report(
        content: bytes, filename: str, **kwargs: Any
    ) -> IngestionReport:
        return IngestionReport(
            document_id=uuid.uuid4(),
            status=IngestionStatus.COMPLETED,
            original_filename=filename,
            file_size_bytes=len(content),
            character_count=100,
            word_count=20,
            token_count=30,
            total_chunks=2,
            total_vectors_stored=2,
            embedding_model="text-embedding-3-small",
            vector_dimension=1536,
            collection_name="investiga_knowledge",
            metrics=IngestionMetrics(total_duration_ms=10.0),
            completed_at=datetime.now(UTC),
        )

    mock_ingestion_pipeline.ingest_content.side_effect = _create_mock_report

    pipeline = ETLPipeline(ingestion_pipeline=mock_ingestion_pipeline)

    config = ETLConfiguration(
        source_type=ETLSource.FILESYSTEM,
        source_path_or_uri=str(sample_etl_dir),
        batch_size=2,
    )
    job = ETLJob(
        user_id=user_id,
        source_type=ETLSource.FILESYSTEM,
        config=config,
    )

    result = await pipeline.execute(job=job, session=mock_session)

    assert result.status == ETLJobStatus.COMPLETED
    assert result.stats.files_discovered > 0
    assert result.stats.files_processed == result.stats.files_discovered
    assert result.stats.files_failed == 0
    assert result.stats.total_chunks > 0
    assert result.stats.total_vectors > 0
    assert len(result.document_ids) == result.stats.files_processed
    assert job.checkpoint_cursor == result.stats.files_discovered


@pytest.mark.asyncio
async def test_etl_pipeline_cancellation(sample_etl_dir: Path) -> None:
    """Test graceful cancellation of in-flight ETL pipeline execution."""
    user_id = uuid.uuid4()
    mock_session = AsyncMock()

    cancel_event = asyncio.Event()

    mock_ingestion_pipeline = MagicMock()

    async def _slow_ingest(*args: Any, **kwargs: Any) -> IngestionReport:
        # Trigger cancellation after first file
        cancel_event.set()
        return IngestionReport(
            document_id=uuid.uuid4(),
            status=IngestionStatus.COMPLETED,
            original_filename="test.txt",
            file_size_bytes=10,
            character_count=10,
            word_count=2,
            token_count=3,
            total_chunks=1,
            total_vectors_stored=1,
            embedding_model="text-embedding-3-small",
            vector_dimension=1536,
            collection_name="investiga_knowledge",
            metrics=IngestionMetrics(total_duration_ms=5.0),
            completed_at=datetime.now(UTC),
        )

    mock_ingestion_pipeline.ingest_content = AsyncMock(side_effect=_slow_ingest)

    pipeline = ETLPipeline(ingestion_pipeline=mock_ingestion_pipeline)

    config = ETLConfiguration(
        source_type=ETLSource.FILESYSTEM,
        source_path_or_uri=str(sample_etl_dir),
        batch_size=1,
    )
    job = ETLJob(
        user_id=user_id,
        source_type=ETLSource.FILESYSTEM,
        config=config,
    )

    result = await pipeline.execute(
        job=job,
        session=mock_session,
        cancellation_token=cancel_event,
    )

    assert result.status == ETLJobStatus.CANCELLED
    assert job.status == ETLJobStatus.CANCELLED
    assert job.checkpoint_cursor >= 1


@pytest.mark.asyncio
async def test_etl_pipeline_resumable_execution(sample_etl_dir: Path) -> None:
    """Test resuming an interrupted ETL job from its checkpoint cursor."""
    user_id = uuid.uuid4()
    mock_session = AsyncMock()

    mock_ingestion_pipeline = MagicMock()
    mock_ingestion_pipeline.ingest_content = AsyncMock(
        return_value=IngestionReport(
            document_id=uuid.uuid4(),
            status=IngestionStatus.COMPLETED,
            original_filename="doc.txt",
            file_size_bytes=50,
            character_count=50,
            word_count=10,
            token_count=15,
            total_chunks=1,
            total_vectors_stored=1,
            embedding_model="test-model",
            vector_dimension=1536,
            collection_name="test_col",
            metrics=IngestionMetrics(total_duration_ms=5.0),
            completed_at=datetime.now(UTC),
        )
    )

    pipeline = ETLPipeline(ingestion_pipeline=mock_ingestion_pipeline)

    # Pre-populate discovered items
    items = [
        ETLDiscoveredItem(
            source_uri=str(sample_etl_dir / "README.md"),
            relative_path="README.md",
            filename="README.md",
            extension=".md",
            size_bytes=20,
        ),
        ETLDiscoveredItem(
            source_uri=str(sample_etl_dir / "app.py"),
            relative_path="app.py",
            filename="app.py",
            extension=".py",
            size_bytes=30,
        ),
        ETLDiscoveredItem(
            source_uri=str(sample_etl_dir / "index.html"),
            relative_path="index.html",
            filename="index.html",
            extension=".html",
            size_bytes=40,
        ),
    ]

    job = ETLJob(
        user_id=user_id,
        source_type=ETLSource.FILESYSTEM,
        config=ETLConfiguration(
            source_type=ETLSource.FILESYSTEM,
            source_path_or_uri=str(sample_etl_dir),
            batch_size=1,
        ),
        discovered_items=items,
        checkpoint_cursor=1,  # Resume from index 1 (skipping README.md)
        stats=ETLStatistics(files_discovered=3, files_processed=1),
    )

    result = await pipeline.execute(job=job, session=mock_session)

    assert result.status == ETLJobStatus.COMPLETED
    # 2 additional files processed after resume
    assert result.stats.files_processed == 3
    assert job.checkpoint_cursor == 3
    # Verify mock was only called for the remaining 2 items
    assert mock_ingestion_pipeline.ingest_content.call_count == 2


@pytest.mark.asyncio
async def test_etl_pipeline_item_failure_isolation(sample_etl_dir: Path) -> None:
    """Test that a failing file does not crash the entire ETL batch and is isolated."""
    user_id = uuid.uuid4()
    mock_session = AsyncMock()

    call_count = 0

    async def _failing_ingest(filename: str, **kwargs: Any) -> IngestionReport:
        nonlocal call_count
        call_count += 1
        if "app.py" in filename:
            raise RuntimeError("Synthetic parsing error on app.py")
        return IngestionReport(
            document_id=uuid.uuid4(),
            status=IngestionStatus.COMPLETED,
            original_filename=filename,
            file_size_bytes=50,
            character_count=50,
            word_count=10,
            token_count=15,
            total_chunks=1,
            total_vectors_stored=1,
            embedding_model="test-model",
            vector_dimension=1536,
            collection_name="test_col",
            metrics=IngestionMetrics(total_duration_ms=5.0),
            completed_at=datetime.now(UTC),
        )

    mock_ingestion_pipeline = MagicMock()
    mock_ingestion_pipeline.ingest_content = AsyncMock(side_effect=_failing_ingest)

    pipeline = ETLPipeline(ingestion_pipeline=mock_ingestion_pipeline)

    config = ETLConfiguration(
        source_type=ETLSource.FILESYSTEM,
        source_path_or_uri=str(sample_etl_dir),
        max_retries_per_file=1,
    )
    job = ETLJob(
        user_id=user_id,
        source_type=ETLSource.FILESYSTEM,
        config=config,
    )

    result = await pipeline.execute(job=job, session=mock_session)

    assert result.status == ETLJobStatus.COMPLETED
    assert result.stats.files_failed == 1
    assert result.stats.files_processed > 0
    assert any("Synthetic parsing error on app.py" in err for err in result.errors)


# =============================================================================
# 5. ETL Service and Scheduler Tests
# =============================================================================


@pytest.mark.asyncio
async def test_etl_service_directory_and_file_ingestion(sample_etl_dir: Path) -> None:
    """Test ETLService high-level methods."""
    user_id = uuid.uuid4()
    mock_session = AsyncMock()

    mock_ingestion = MagicMock()
    mock_ingestion.ingest_content = AsyncMock(
        return_value=IngestionReport(
            document_id=uuid.uuid4(),
            status=IngestionStatus.COMPLETED,
            original_filename="doc.txt",
            file_size_bytes=10,
            character_count=10,
            word_count=2,
            token_count=3,
            total_chunks=1,
            total_vectors_stored=1,
            embedding_model="test",
            vector_dimension=1536,
            collection_name="test",
            metrics=IngestionMetrics(total_duration_ms=1.0),
            completed_at=datetime.now(UTC),
        )
    )

    pipeline = ETLPipeline(ingestion_pipeline=mock_ingestion)
    service = ETLService(pipeline=pipeline)

    # Ingest directory
    dir_res = await service.ingest_directory(
        user_id=user_id,
        directory_path=sample_etl_dir,
        session=mock_session,
    )
    assert dir_res.status == ETLJobStatus.COMPLETED

    # Query job status
    job = await service.job_status(dir_res.job_id)
    assert job.status == ETLJobStatus.COMPLETED

    # List jobs
    user_jobs = await service.list_jobs(user_id=user_id)
    assert len(user_jobs) == 1

    # Ingest explicit files
    files_res = await service.ingest_files(
        user_id=user_id,
        file_paths=[sample_etl_dir / "README.md", sample_etl_dir / "app.py"],
        session=mock_session,
    )
    assert files_res.status == ETLJobStatus.COMPLETED


def test_etl_scheduler_mechanics() -> None:
    """Test ETLScheduler registration, frequencies, and cancellation."""
    scheduler = ETLScheduler()
    job_id = uuid.uuid4()

    # Schedule hourly job
    sched_id = scheduler.schedule_job(
        job_id=job_id,
        schedule_type="hourly",
    )
    entry = scheduler.get_schedule(sched_id)
    assert entry is not None
    assert entry.frequency == ScheduleFrequency.HOURLY
    assert entry.is_active is True
    assert entry.next_run_at is not None

    # List active schedules
    active = scheduler.list_schedules(active_only=True)
    assert len(active) == 1

    # Cancel schedule
    cancelled = scheduler.cancel_schedule(sched_id)
    assert cancelled is True
    assert entry.is_active is False
    assert len(scheduler.list_schedules(active_only=True)) == 0
