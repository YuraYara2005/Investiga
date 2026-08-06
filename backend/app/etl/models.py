"""ETL Data Models and Schemas for Investiga.

Defines Pydantic models for data sources, discovery items, streaming payloads,
ETL configuration, execution statistics, job state tracking, and batch results.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ETLSource(StrEnum):
    """Supported and extensible ETL data source identifiers."""

    FILESYSTEM = "filesystem"
    GITHUB = "github"
    WEBSITE = "website"
    API = "api"
    SHAREPOINT = "sharepoint"
    GDRIVE = "gdrive"
    NOTION = "notion"
    CONFLUENCE = "confluence"


class ETLJobStatus(StrEnum):
    """Lifecycle states for ETL execution jobs."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class ETLDiscoveredItem(BaseModel):
    """Metadata representing a single item discovered at an external source before payload download."""

    model_config = ConfigDict(frozen=True)

    source_uri: str = Field(
        ...,
        description="Canonical source URI or absolute path uniquely identifying the item.",
    )
    relative_path: str = Field(
        ...,
        description="Relative path of the item from the source root.",
    )
    filename: str = Field(
        ...,
        description="Original name of the file or asset.",
    )
    extension: str = Field(
        ...,
        description="Lowercased file extension including leading period.",
    )
    size_bytes: int = Field(
        default=0,
        ge=0,
        description="File size in bytes if available from source metadata.",
    )
    modified_at: datetime | None = Field(
        default=None,
        description="Timestamp of last modification at source if available.",
    )
    mime_type: str | None = Field(
        default=None,
        description="MIME type inferred or provided by source header.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary source-specific metadata attributes.",
    )


class ETLDocumentStreamItem(BaseModel):
    """Materialized document payload ready for handoff to Storage and Document Ingestion Pipeline."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    content: bytes = Field(
        ...,
        description="Raw byte content of the document.",
    )
    filename: str = Field(
        ...,
        description="Original filename to be registered in Storage.",
    )
    source_uri: str = Field(
        ...,
        description="Origin source URI or file path for traceability.",
    )
    mime_type: str | None = Field(
        default=None,
        description="Verified or reported MIME type.",
    )
    title: str | None = Field(
        default=None,
        description="Optional human-readable title.",
    )
    category: str | None = Field(
        default=None,
        description="Optional knowledge category tag.",
    )
    size_bytes: int = Field(
        ...,
        ge=0,
        description="Actual payload size in bytes.",
    )
    checksum: str | None = Field(
        default=None,
        description="SHA-256 hex checksum of payload.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Contextual metadata extracted during ingestion.",
    )


class ETLStatistics(BaseModel):
    """Runtime telemetry and throughput statistics for an ETL job."""

    files_discovered: int = Field(
        default=0,
        ge=0,
        description="Total count of candidate items discovered by the loader.",
    )
    files_processed: int = Field(
        default=0,
        ge=0,
        description="Count of files successfully ingested into knowledge base.",
    )
    files_skipped: int = Field(
        default=0,
        ge=0,
        description="Count of files skipped due to filtering, duplicates, or size limits.",
    )
    files_failed: int = Field(
        default=0,
        ge=0,
        description="Count of files that failed during processing or vectorization.",
    )
    bytes_processed: int = Field(
        default=0,
        ge=0,
        description="Total volume of bytes ingested.",
    )
    total_chunks: int = Field(
        default=0,
        ge=0,
        description="Total text chunks generated and stored.",
    )
    total_vectors: int = Field(
        default=0,
        ge=0,
        description="Total vector embeddings generated and indexed in vector database.",
    )
    elapsed_time_seconds: float = Field(
        default=0.0,
        ge=0.0,
        description="Total elapsed wall-clock time in seconds.",
    )
    throughput_files_per_second: float = Field(
        default=0.0,
        ge=0.0,
        description="Ingestion throughput in files per second.",
    )
    throughput_bytes_per_second: float = Field(
        default=0.0,
        ge=0.0,
        description="Ingestion throughput in bytes per second.",
    )
    ingestion_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when statistics were recorded or updated.",
    )

    def calculate_throughput(self) -> None:
        """Update throughput rates based on processed counts and elapsed time."""
        if self.elapsed_time_seconds > 0:
            self.throughput_files_per_second = round(
                self.files_processed / self.elapsed_time_seconds, 2
            )
            self.throughput_bytes_per_second = round(
                self.bytes_processed / self.elapsed_time_seconds, 2
            )


class ETLConfiguration(BaseModel):
    """Configurable ingestion rules, filters, and pipeline parameters."""

    source_type: ETLSource = Field(
        default=ETLSource.FILESYSTEM,
        description="Identifier of the target loader source.",
    )
    source_path_or_uri: str = Field(
        ...,
        description="Root path, URL, repository name, or endpoint to ingest.",
    )
    include_patterns: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Glob patterns of file paths or names to include.",
    )
    exclude_patterns: list[str] = Field(
        default_factory=list,
        description="Glob patterns of file paths or names to exclude.",
    )
    allowed_extensions: list[str] | None = Field(
        default=None,
        description="Explicit allowed extensions list. If None, uses storage defaults.",
    )
    recursive: bool = Field(
        default=True,
        description="Whether to recursively traverse child directories or subtrees.",
    )
    follow_symlinks: bool = Field(
        default=False,
        description="Whether to follow symbolic links during filesystem traversal.",
    )
    ignore_hidden: bool = Field(
        default=True,
        description="Whether to ignore hidden files and directories (starting with .).",
    )
    batch_size: int = Field(
        default=10,
        ge=1,
        le=500,
        description="Number of files to process per concurrent batch.",
    )
    max_files: int | None = Field(
        default=None,
        ge=1,
        description="Maximum number of files to discover and process in one job.",
    )
    max_file_size_bytes: int = Field(
        default=50 * 1024 * 1024,
        ge=1,
        description="Maximum permitted file size in bytes (default 50MB).",
    )
    force_reindex: bool = Field(
        default=False,
        description="Whether to overwrite existing embeddings and force document re-ingestion.",
    )
    chunk_size: int | None = Field(
        default=None,
        ge=50,
        le=8192,
        description="Optional override for chunk token target size.",
    )
    chunk_overlap: int | None = Field(
        default=None,
        ge=0,
        description="Optional override for chunk overlap size.",
    )
    category: str | None = Field(
        default=None,
        description="Optional default category for ingested documents.",
    )
    max_retries_per_file: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Maximum retry attempts per file if transient error occurs.",
    )
    extra_options: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional loader-specific parameters (e.g. auth tokens, branch names).",
    )


class ETLJob(BaseModel):
    """Complete state, telemetry, and checkpoint record for an ETL ingestion job."""

    job_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        description="Unique identifier for this ETL execution job.",
    )
    user_id: uuid.UUID = Field(
        ...,
        description="User UUID who initiated or owns this ETL job.",
    )
    source_type: ETLSource = Field(
        ...,
        description="Source type being ingested.",
    )
    config: ETLConfiguration = Field(
        ...,
        description="Configuration parameters governing this job.",
    )
    status: ETLJobStatus = Field(
        default=ETLJobStatus.PENDING,
        description="Current execution state.",
    )
    stats: ETLStatistics = Field(
        default_factory=ETLStatistics,
        description="Real-time telemetry and throughput metrics.",
    )
    discovered_items: list[ETLDiscoveredItem] = Field(
        default_factory=list,
        description="List of items discovered at source.",
    )
    processed_document_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="List of KnowledgeDocument IDs successfully generated.",
    )
    skipped_paths: list[str] = Field(
        default_factory=list,
        description="List of paths skipped during execution.",
    )
    failed_paths: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of failed item paths to error messages.",
    )
    error_message: str | None = Field(
        default=None,
        description="Fatal error message if job failed entirely.",
    )
    checkpoint_cursor: int = Field(
        default=0,
        ge=0,
        description="Index of last processed item in discovered_items for resumability.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Creation timestamp.",
    )
    started_at: datetime | None = Field(
        default=None,
        description="Timestamp when execution started.",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="Timestamp when execution ended.",
    )


class ETLResult(BaseModel):
    """Final result payload summarizing job completion and outputs."""

    job_id: uuid.UUID = Field(
        ...,
        description="Job identifier.",
    )
    status: ETLJobStatus = Field(
        ...,
        description="Final completion status.",
    )
    source: ETLSource = Field(
        ...,
        description="ETL source type.",
    )
    stats: ETLStatistics = Field(
        ...,
        description="Summary statistics.",
    )
    document_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="List of created KnowledgeDocument IDs.",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="List of error messages encountered during job.",
    )
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp of job completion.",
    )
