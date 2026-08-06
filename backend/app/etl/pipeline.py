"""Enterprise ETL Ingestion Pipeline for Investiga.

Coordinates the end-to-end data lifecycle from source discovery and streaming
through storage registration, document parsing, semantic chunking, vector embedding,
and knowledge repository persistence.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.etl.exceptions import (
    ETLJobCancelledException,
    ETLJobExecutionException,
    ETLPipelineException,
)
from app.etl.interfaces import BaseLoaderInterface, ETLPipelineInterface
from app.etl.models import (
    ETLDiscoveredItem,
    ETLJob,
    ETLJobStatus,
    ETLResult,
)
from app.etl.registry import LoaderRegistry, get_loader_registry
from app.ingestion.models import IngestionOptions
from app.ingestion.pipeline import DocumentIngestionPipeline

logger = get_logger(__name__)


class ETLPipeline(ETLPipelineInterface):
    """Orchestrates multi-source ETL extraction and connects to the core ingestion pipeline."""

    def __init__(
        self,
        loader_registry: LoaderRegistry | None = None,
        ingestion_pipeline: DocumentIngestionPipeline | None = None,
    ) -> None:
        """Initialize ETL pipeline with loader registry and document ingestion pipeline."""
        self._registry = loader_registry or get_loader_registry()
        self._ingestion_pipeline = ingestion_pipeline or DocumentIngestionPipeline()

    async def execute(
        self,
        job: ETLJob,
        session: AsyncSession,
        cancellation_token: asyncio.Event | None = None,
    ) -> ETLResult:
        """Execute end-to-end ETL job processing discovered source files into knowledge base."""
        start_time = time.perf_counter()
        job.started_at = datetime.now(UTC)
        job.status = ETLJobStatus.RUNNING

        loader: BaseLoaderInterface = self._registry.get(job.source_type)

        logger.info(
            "etl_pipeline_job_started",
            job_id=str(job.job_id),
            source_type=job.source_type.value,
            source_uri=job.config.source_path_or_uri,
            resume_cursor=job.checkpoint_cursor,
        )

        try:
            # 1. Discovery Phase (if discovered_items is empty, discover from source)
            if not job.discovered_items:
                logger.info("etl_discovery_started", job_id=str(job.job_id))
                async for item in loader.discover(job.config):
                    if cancellation_token and cancellation_token.is_set():
                        raise ETLJobCancelledException(job_id=job.job_id)
                    job.discovered_items.append(item)
                    job.stats.files_discovered += 1

                logger.info(
                    "etl_discovery_completed",
                    job_id=str(job.job_id),
                    total_discovered=job.stats.files_discovered,
                )

            # Check for zero files discovered
            if not job.discovered_items:
                job.status = ETLJobStatus.COMPLETED
                job.completed_at = datetime.now(UTC)
                job.stats.elapsed_time_seconds = round(
                    time.perf_counter() - start_time, 2
                )
                return ETLResult(
                    job_id=job.job_id,
                    status=job.status,
                    source=job.source_type,
                    stats=job.stats,
                    document_ids=[],
                    errors=[],
                    completed_at=job.completed_at,
                )

            # 2. Ingestion & Vectorization Processing Loop
            total_items = len(job.discovered_items)
            cursor = job.checkpoint_cursor
            batch_size = job.config.batch_size

            # Ingestion options mapping
            ingestion_opts = IngestionOptions(
                chunk_size=job.config.chunk_size,
                overlap=job.config.chunk_overlap,
                force_reindex=job.config.force_reindex,
                batch_size=job.config.batch_size,
            )

            while cursor < total_items:
                # Check for cancellation before each batch
                if cancellation_token and cancellation_token.is_set():
                    logger.warning(
                        "etl_job_cancellation_requested",
                        job_id=str(job.job_id),
                        cursor=cursor,
                    )
                    job.status = ETLJobStatus.CANCELLED
                    raise ETLJobCancelledException(job_id=job.job_id)

                batch_end = min(cursor + batch_size, total_items)
                current_batch = job.discovered_items[cursor:batch_end]

                for item in current_batch:
                    if cancellation_token and cancellation_token.is_set():
                        job.status = ETLJobStatus.CANCELLED
                        raise ETLJobCancelledException(job_id=job.job_id)

                    await self._process_single_item(
                        item=item,
                        loader=loader,
                        job=job,
                        session=session,
                        options=ingestion_opts,
                    )

                    # Advance checkpoint cursor per item
                    job.checkpoint_cursor += 1

                # Update elapsed time & throughput after each batch
                job.stats.elapsed_time_seconds = round(
                    time.perf_counter() - start_time, 2
                )
                job.stats.calculate_throughput()

                cursor = job.checkpoint_cursor

            # 3. Finalize Job State
            job.status = ETLJobStatus.COMPLETED
            job.completed_at = datetime.now(UTC)
            job.stats.elapsed_time_seconds = round(time.perf_counter() - start_time, 2)
            job.stats.calculate_throughput()

            logger.info(
                "etl_pipeline_job_completed",
                job_id=str(job.job_id),
                processed=job.stats.files_processed,
                failed=job.stats.files_failed,
                skipped=job.stats.files_skipped,
                total_chunks=job.stats.total_chunks,
                total_vectors=job.stats.total_vectors,
                duration_seconds=job.stats.elapsed_time_seconds,
            )

            return ETLResult(
                job_id=job.job_id,
                status=job.status,
                source=job.source_type,
                stats=job.stats,
                document_ids=job.processed_document_ids,
                errors=list(job.failed_paths.values()),
                completed_at=job.completed_at,
            )

        except ETLJobCancelledException:
            job.status = ETLJobStatus.CANCELLED
            job.completed_at = datetime.now(UTC)
            job.stats.elapsed_time_seconds = round(time.perf_counter() - start_time, 2)
            job.stats.calculate_throughput()
            return ETLResult(
                job_id=job.job_id,
                status=ETLJobStatus.CANCELLED,
                source=job.source_type,
                stats=job.stats,
                document_ids=job.processed_document_ids,
                errors=["Job was cancelled."],
                completed_at=job.completed_at,
            )

        except Exception as exc:
            job.status = ETLJobStatus.FAILED
            job.error_message = str(exc)
            job.completed_at = datetime.now(UTC)
            job.stats.elapsed_time_seconds = round(time.perf_counter() - start_time, 2)
            job.stats.calculate_throughput()

            logger.error(
                "etl_pipeline_fatal_error",
                job_id=str(job.job_id),
                error=str(exc),
                exc_info=True,
            )

            if isinstance(exc, ETLPipelineException):
                raise exc

            raise ETLJobExecutionException(
                message=f"ETL pipeline failed: {exc}",
                job_id=job.job_id,
                details={"error": str(exc)},
            ) from exc

    async def _process_single_item(
        self,
        item: ETLDiscoveredItem,
        loader: BaseLoaderInterface,
        job: ETLJob,
        session: AsyncSession,
        options: IngestionOptions,
    ) -> None:
        """Load single item, execute ingestion pipeline with retry policy, and update job stats."""
        max_retries = job.config.max_retries_per_file
        attempt = 0
        last_error: Exception | None = None

        while attempt <= max_retries:
            try:
                # Materialize stream item from loader
                stream_item = await loader.load(item, job.config)

                # Feed stream item into standard DocumentIngestionPipeline
                report = await self._ingestion_pipeline.ingest_content(
                    content=stream_item.content,
                    filename=stream_item.filename,
                    user_id=job.user_id,
                    session=session,
                    mime_type=stream_item.mime_type,
                    title=stream_item.title,
                    category=stream_item.category or job.config.category,
                    options=options,
                )

                # Update job success metrics
                job.processed_document_ids.append(report.document_id)
                job.stats.files_processed += 1
                job.stats.bytes_processed += stream_item.size_bytes
                job.stats.total_chunks += report.total_chunks
                job.stats.total_vectors += report.total_vectors_stored
                return

            except Exception as exc:
                last_error = exc
                attempt += 1
                if attempt <= max_retries:
                    logger.warning(
                        "etl_item_retry_attempt",
                        path=item.source_uri,
                        attempt=attempt,
                        max_retries=max_retries,
                        error=str(exc),
                    )
                    await asyncio.sleep(0.2 * attempt)
                else:
                    break

        # If retries exhausted, mark as failed
        err_msg = str(last_error) if last_error else "Unknown processing error"
        logger.error(
            "etl_item_processing_failed",
            path=item.source_uri,
            error=err_msg,
        )
        job.failed_paths[item.source_uri] = err_msg
        job.stats.files_failed += 1
