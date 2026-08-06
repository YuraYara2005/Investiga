"""High-Level Application Service for Enterprise ETL Ingestion.

Provides unified orchestration for directory ingestion, single/multi-file ETL jobs,
asynchronous cancellation, resumable checkpoints, and job telemetry queries.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.etl.exceptions import (
    ETLJobNotFoundException,
    ETLValidationException,
)
from app.etl.models import (
    ETLConfiguration,
    ETLJob,
    ETLJobStatus,
    ETLResult,
    ETLSource,
)
from app.etl.pipeline import ETLPipeline
from app.etl.registry import LoaderRegistry, get_loader_registry

logger = get_logger(__name__)


class ETLService:
    """Enterprise ETL Application Service coordinating loaders and pipeline execution."""

    def __init__(
        self,
        pipeline: ETLPipeline | None = None,
        loader_registry: LoaderRegistry | None = None,
    ) -> None:
        """Initialize ETL Service with pipeline and registry dependencies."""
        self._registry = loader_registry or get_loader_registry()
        self._pipeline = pipeline or ETLPipeline(loader_registry=self._registry)
        self._jobs: dict[uuid.UUID, ETLJob] = {}
        self._cancellation_tokens: dict[uuid.UUID, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    @property
    def pipeline(self) -> ETLPipeline:
        """Access the underlying ETL execution pipeline."""
        return self._pipeline

    @property
    def loader_registry(self) -> LoaderRegistry:
        """Access the underlying loader registry."""
        return self._registry

    async def ingest_directory(
        self,
        user_id: uuid.UUID,
        directory_path: str | Path,
        session: AsyncSession,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        allowed_extensions: list[str] | None = None,
        recursive: bool = True,
        batch_size: int = 10,
        max_files: int | None = None,
        force_reindex: bool = False,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        category: str | None = None,
        extra_options: dict[str, Any] | None = None,
    ) -> ETLResult:
        """Create and immediately execute an ETL job scanning a local directory tree.

        Args:
            user_id: Principal user initiating ingestion.
            directory_path: Root filesystem directory path.
            session: Active database session.
            include_patterns: Optional glob include list.
            exclude_patterns: Optional glob exclude list.
            allowed_extensions: Optional extensions filter.
            recursive: Whether to scan recursively.
            batch_size: Processing batch size.
            max_files: Optional cap on files to process.
            force_reindex: Overwrite existing vector embeddings.
            chunk_size: Target token size per chunk.
            chunk_overlap: Chunk overlap size.
            category: Optional knowledge category.
            extra_options: Additional loader options.

        Returns:
            ETLResult: Complete execution result and summary.
        """
        resolved_path = str(Path(directory_path).resolve())

        config = ETLConfiguration(
            source_type=ETLSource.FILESYSTEM,
            source_path_or_uri=resolved_path,
            include_patterns=include_patterns or ["*"],
            exclude_patterns=exclude_patterns or [],
            allowed_extensions=allowed_extensions,
            recursive=recursive,
            batch_size=batch_size,
            max_files=max_files,
            force_reindex=force_reindex,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            category=category,
            extra_options=extra_options or {},
        )

        job = ETLJob(
            user_id=user_id,
            source_type=ETLSource.FILESYSTEM,
            config=config,
            status=ETLJobStatus.PENDING,
        )

        async with self._lock:
            self._jobs[job.job_id] = job
            cancel_token = asyncio.Event()
            self._cancellation_tokens[job.job_id] = cancel_token

        logger.info(
            "etl_service_directory_job_created",
            job_id=str(job.job_id),
            directory=resolved_path,
            user_id=str(user_id),
        )

        try:
            return await self._pipeline.execute(
                job=job,
                session=session,
                cancellation_token=cancel_token,
            )
        finally:
            async with self._lock:
                self._cancellation_tokens.pop(job.job_id, None)

    async def ingest_files(
        self,
        user_id: uuid.UUID,
        file_paths: list[str | Path],
        session: AsyncSession,
        batch_size: int = 10,
        force_reindex: bool = False,
        category: str | None = None,
    ) -> ETLResult:
        """Ingest an explicit list of local file paths via ETL pipeline."""
        if not file_paths:
            raise ETLValidationException(
                message="File paths list cannot be empty.",
                source=ETLSource.FILESYSTEM.value,
            )

        # Build composite job
        common_parent = str(Path(file_paths[0]).parent.resolve())
        includes = [Path(p).name for p in file_paths]

        config = ETLConfiguration(
            source_type=ETLSource.FILESYSTEM,
            source_path_or_uri=common_parent,
            include_patterns=includes,
            recursive=False,
            batch_size=batch_size,
            force_reindex=force_reindex,
            category=category,
        )

        job = ETLJob(
            user_id=user_id,
            source_type=ETLSource.FILESYSTEM,
            config=config,
            status=ETLJobStatus.PENDING,
        )

        async with self._lock:
            self._jobs[job.job_id] = job
            cancel_token = asyncio.Event()
            self._cancellation_tokens[job.job_id] = cancel_token

        try:
            return await self._pipeline.execute(
                job=job,
                session=session,
                cancellation_token=cancel_token,
            )
        finally:
            async with self._lock:
                self._cancellation_tokens.pop(job.job_id, None)

    async def resume_job(
        self,
        job_id: uuid.UUID,
        session: AsyncSession,
    ) -> ETLResult:
        """Resume an interrupted, paused, or failed ETL job from its last checkpoint cursor.

        Args:
            job_id: UUID of the job to resume.
            session: Active database session.

        Returns:
            ETLResult: Result of resumed execution.
        """
        job = await self.job_status(job_id)

        if job.status == ETLJobStatus.COMPLETED:
            return ETLResult(
                job_id=job.job_id,
                status=job.status,
                source=job.source_type,
                stats=job.stats,
                document_ids=job.processed_document_ids,
                errors=list(job.failed_paths.values()),
                completed_at=job.completed_at or job.created_at,
            )

        async with self._lock:
            cancel_token = asyncio.Event()
            self._cancellation_tokens[job.job_id] = cancel_token

        logger.info(
            "etl_service_resuming_job",
            job_id=str(job.job_id),
            cursor=job.checkpoint_cursor,
        )

        try:
            return await self._pipeline.execute(
                job=job,
                session=session,
                cancellation_token=cancel_token,
            )
        finally:
            async with self._lock:
                self._cancellation_tokens.pop(job.job_id, None)

    async def cancel_job(self, job_id: uuid.UUID) -> bool:
        """Trigger cancellation for an in-flight ETL execution job.

        Args:
            job_id: UUID of the running job.

        Returns:
            bool: True if cancellation token was signaled.
        """
        async with self._lock:
            token = self._cancellation_tokens.get(job_id)
            if token is not None:
                token.set()
                logger.info("etl_service_cancel_signal_sent", job_id=str(job_id))
                return True

            job = self._jobs.get(job_id)
            if job and job.status in {ETLJobStatus.PENDING, ETLJobStatus.RUNNING}:
                job.status = ETLJobStatus.CANCELLED
                return True

        return False

    async def job_status(self, job_id: uuid.UUID) -> ETLJob:
        """Retrieve current state and metrics for an ETL job."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise ETLJobNotFoundException(job_id=job_id)
            return job

    async def list_jobs(
        self,
        user_id: uuid.UUID | None = None,
        status: ETLJobStatus | None = None,
    ) -> list[ETLJob]:
        """List registered ETL jobs filtered by user and status."""
        async with self._lock:
            jobs = list(self._jobs.values())

        if user_id is not None:
            jobs = [j for j in jobs if j.user_id == user_id]
        if status is not None:
            jobs = [j for j in jobs if j.status == status]

        return sorted(jobs, key=lambda j: j.created_at, reverse=True)
