"""End-to-End Document Ingestion Pipeline Orchestrator for Investiga.

Connects Storage, Document Processing, Text Cleaning, Intelligent Chunking,
Embedding Generation, Qdrant Vector Storage, Relational KnowledgeChunk Persistence,
and KnowledgeDocument lifecycle management into a single robust, non-blocking workflow.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chunking.chunker import ChunkingEngine
from app.chunking.exceptions import ChunkingException
from app.common.events.dispatcher import (
    EventDispatcherInterface,
    get_event_dispatcher,
)
from app.common.events.events import (
    DocumentChunked,
    DocumentParsed,
    DocumentUploaded,
    EmbeddingsGenerated,
    IngestionCompleted,
    IngestionFailed,
    VectorsIndexed,
)
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.document_processing.exceptions import DocumentProcessingException
from app.document_processing.processor import DocumentProcessor
from app.embeddings.embedding_service import (
    EmbeddingService,
    create_embedding_service,
)
from app.embeddings.exceptions import EmbeddingException
from app.ingestion.exceptions import (
    DatabasePersistenceStageException,
    DocumentAlreadyProcessingException,
    DocumentChunkingStageException,
    DocumentNotFoundException,
    DocumentParsingStageException,
    EmbeddingStageException,
    IngestionPipelineException,
    StorageReadException,
    VectorIndexingStageException,
)
from app.ingestion.interfaces import DocumentIngestionPipelineInterface
from app.ingestion.models import (
    IngestionMetrics,
    IngestionOptions,
    IngestionReport,
    IngestionStatus,
)
from app.knowledge.models import (
    EmbeddingStatus,
    KnowledgeChunk,
    KnowledgeDocument,
    ProcessingStatus,
)
from app.knowledge.repositories.knowledge_chunk_repository import (
    KnowledgeChunkRepository,
)
from app.storage.local_storage import LocalStorageProvider
from app.storage.storage_service import StorageService
from app.vectorstore.exceptions import VectorStoreException
from app.vectorstore.models import VectorPayload, VectorRecord
from app.vectorstore.qdrant_provider import QdrantProvider
from app.vectorstore.vector_index_manager import VectorIndexManager
from app.vectorstore.vector_repository import VectorRepository

logger = get_logger(__name__)


class DocumentIngestionPipeline(DocumentIngestionPipelineInterface):
    """Enterprise document ingestion and vectorization orchestration engine."""

    def __init__(
        self,
        storage_service: StorageService | None = None,
        document_processor: DocumentProcessor | None = None,
        chunking_engine: ChunkingEngine | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_repository: VectorRepository | None = None,
        vector_index_manager: VectorIndexManager | None = None,
        event_dispatcher: EventDispatcherInterface | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize pipeline with injected subsystem dependencies or defaults.

        Args:
            storage_service: Storage service for reading physical files.
            document_processor: Document processing & text normalization pipeline.
            chunking_engine: Semantic text partitioning engine.
            embedding_service: Embedding model inference service.
            vector_repository: Qdrant / Vector store persistence abstraction.
            vector_index_manager: Vector collection lifecycle and schema manager.
            event_dispatcher: In-process domain event publishing dispatcher.
            settings: Root application configuration instance.
        """
        self._settings = settings or get_settings()
        self._storage_service = storage_service or StorageService(
            provider=LocalStorageProvider(
                base_directory=self._settings.storage.upload_directory
            )
        )
        self._document_processor = document_processor or DocumentProcessor()
        self._chunking_engine = chunking_engine or ChunkingEngine(
            chunk_size=self._settings.chunking.chunk_size,
            overlap=self._settings.chunking.overlap,
            strategy=self._settings.chunking.strategy,
        )
        self._embedding_service = embedding_service or create_embedding_service()

        qdrant_prov = QdrantProvider(settings=self._settings.vectorstore)
        self._vector_repository = vector_repository or VectorRepository(
            provider=qdrant_prov,
            settings=self._settings.vectorstore,
        )
        self._vector_index_manager = vector_index_manager or VectorIndexManager(
            provider=qdrant_prov,
            settings=self._settings.vectorstore,
        )
        self._event_dispatcher = event_dispatcher or get_event_dispatcher()

        # In-flight document locks to prevent concurrent ingestion of the same document
        self._document_locks: dict[uuid.UUID, asyncio.Lock] = {}
        self._registry_lock = asyncio.Lock()

    async def _acquire_document_lock(self, document_id: uuid.UUID) -> asyncio.Lock:
        """Atomically acquire or create a concurrency lock for a specific document ID."""
        async with self._registry_lock:
            if document_id not in self._document_locks:
                self._document_locks[document_id] = asyncio.Lock()
            lock = self._document_locks[document_id]

        if lock.locked():
            logger.warning(
                "document_ingestion_concurrency_conflict",
                document_id=str(document_id),
            )
            raise DocumentAlreadyProcessingException(document_id=document_id)

        await lock.acquire()
        return lock

    async def _release_document_lock(
        self, document_id: uuid.UUID, lock: asyncio.Lock
    ) -> None:
        """Safely release and clean up the concurrency lock."""
        try:
            if lock.locked():
                lock.release()
        finally:
            async with self._registry_lock:
                if (
                    document_id in self._document_locks
                    and not self._document_locks[document_id].locked()
                ):
                    self._document_locks.pop(document_id, None)

    async def ingest_document(
        self,
        document_id: uuid.UUID,
        session: AsyncSession,
        options: IngestionOptions | None = None,
    ) -> IngestionReport:
        """Execute the complete end-to-end ingestion pipeline for a registered document."""
        options = options or IngestionOptions()
        lock = await self._acquire_document_lock(document_id)
        start_time = time.perf_counter()
        current_stage = "initialization"

        parsing_duration_ms = 0.0
        cleaning_duration_ms = 0.0
        chunking_duration_ms = 0.0
        embedding_duration_ms = 0.0
        vector_upload_duration_ms = 0.0
        database_duration_ms = 0.0

        document: KnowledgeDocument | None = None

        try:
            # -----------------------------------------------------------------
            # 1. State Validation & Transition -> PROCESSING
            # -----------------------------------------------------------------
            current_stage = "state_validation"
            document = await session.get(KnowledgeDocument, document_id)
            if document is None or document.is_deleted:
                raise DocumentNotFoundException(document_id=document_id)

            if (
                document.processing_status == ProcessingStatus.PROCESSING
                and not options.force_reindex
            ):
                raise DocumentAlreadyProcessingException(document_id=document_id)

            document.processing_status = ProcessingStatus.PROCESSING
            document.embedding_status = EmbeddingStatus.QUEUED
            document.updated_at = datetime.now(UTC)
            await session.commit()

            logger.info(
                "ingestion_pipeline_started",
                document_id=str(document.id),
                filename=document.original_filename,
                user_id=str(document.uploaded_by),
            )

            # -----------------------------------------------------------------
            # 2. Storage Content Retrieval
            # -----------------------------------------------------------------
            current_stage = "storage_read"
            content_bytes: bytes = b""
            try:
                if self._storage_service and document.stored_filename:
                    content_bytes = await self._storage_service.read_file(
                        document.stored_filename
                    )
                elif document.storage_path and Path(document.storage_path).exists():
                    content_bytes = Path(document.storage_path).read_bytes()
                else:
                    raise FileNotFoundError(
                        f"Storage path '{document.storage_path}' inaccessible."
                    )
            except Exception as exc:
                raise StorageReadException(
                    document_id=document.id,
                    storage_path=document.storage_path,
                    reason=str(exc),
                ) from exc

            await self._event_dispatcher.publish(
                DocumentUploaded(
                    document_id=document.id,
                    user_id=document.uploaded_by,
                    original_filename=document.original_filename,
                    stored_filename=document.stored_filename,
                    file_size_bytes=document.file_size,
                    checksum=document.checksum,
                    mime_type=document.mime_type,
                )
            )

            # -----------------------------------------------------------------
            # 3. Document Processing & Text Cleaning
            # -----------------------------------------------------------------
            current_stage = "parsing_and_cleaning"
            parse_start = time.perf_counter()
            try:
                proc_result = await self._document_processor.process(
                    content=content_bytes,
                    filename=document.original_filename,
                    mime_type=document.mime_type,
                    document_id=document.id,
                    language=document.language,
                )
            except DocumentProcessingException as exc:
                raise DocumentParsingStageException(
                    document_id=document.id,
                    filename=document.original_filename,
                    reason=str(exc),
                ) from exc
            except Exception as exc:
                raise DocumentParsingStageException(
                    document_id=document.id,
                    filename=document.original_filename,
                    reason=f"Unexpected extraction error: {exc}",
                ) from exc

            parsing_duration_ms = (time.perf_counter() - parse_start) * 1000.0

            logger.info(
                "ingestion_parsing_completed",
                document_id=str(document.id),
                char_count=proc_result.character_count,
                word_count=proc_result.word_count,
                page_count=proc_result.page_count,
                duration_ms=round(parsing_duration_ms, 2),
            )

            await self._event_dispatcher.publish(
                DocumentParsed(
                    document_id=document.id,
                    character_count=proc_result.character_count,
                    word_count=proc_result.word_count,
                    page_count=proc_result.page_count,
                    duration_ms=parsing_duration_ms,
                )
            )

            # -----------------------------------------------------------------
            # 4. Intelligent Chunking
            # -----------------------------------------------------------------
            current_stage = "chunking"
            chunk_start = time.perf_counter()

            effective_chunker = self._chunking_engine
            if (
                options.chunk_size is not None
                or options.overlap is not None
                or options.chunk_strategy is not None
            ):
                effective_chunker = ChunkingEngine(
                    chunk_size=options.chunk_size or self._settings.chunking.chunk_size,
                    overlap=options.overlap
                    if options.overlap is not None
                    else self._settings.chunking.overlap,
                    strategy=options.chunk_strategy or self._settings.chunking.strategy,
                )

            try:
                chunk_result = await effective_chunker.chunk_async(
                    text=proc_result.clean_text,
                    document_id=document.id,
                    source_filename=document.original_filename,
                    language=proc_result.language or "en",
                    extra_metadata=options.metadata_override,
                )
            except ChunkingException as exc:
                raise DocumentChunkingStageException(
                    document_id=document.id,
                    strategy=effective_chunker.strategy_name,
                    reason=str(exc),
                ) from exc
            except Exception as exc:
                raise DocumentChunkingStageException(
                    document_id=document.id,
                    strategy=effective_chunker.strategy_name,
                    reason=f"Unexpected chunking error: {exc}",
                ) from exc

            chunking_duration_ms = (time.perf_counter() - chunk_start) * 1000.0

            logger.info(
                "ingestion_chunking_completed",
                document_id=str(document.id),
                chunk_count=chunk_result.total_chunks,
                total_tokens=chunk_result.total_tokens,
                strategy=chunk_result.strategy_used,
                duration_ms=round(chunking_duration_ms, 2),
            )

            await self._event_dispatcher.publish(
                DocumentChunked(
                    document_id=document.id,
                    chunk_count=chunk_result.total_chunks,
                    total_tokens=chunk_result.total_tokens,
                    strategy=chunk_result.strategy_used,
                    duration_ms=chunking_duration_ms,
                )
            )

            # -----------------------------------------------------------------
            # 5. Idempotent Vector & Chunk Cleanup
            # -----------------------------------------------------------------
            current_stage = "idempotency_cleanup"
            chunk_repo = KnowledgeChunkRepository(session=session)
            await chunk_repo.delete_by_document_id(document.id)

            if self._vector_repository is not None:
                try:
                    await self._vector_repository.delete_by_document(document.id)
                except Exception as exc:
                    logger.debug("vector_cleanup_skipped_or_not_found", error=str(exc))

            # -----------------------------------------------------------------
            # 6. Embedding Generation
            # -----------------------------------------------------------------
            current_stage = "embedding_generation"
            embed_start = time.perf_counter()

            chunk_texts = [c.text for c in chunk_result.chunks]
            chunk_ids = [str(c.chunk_id) for c in chunk_result.chunks]

            try:
                batch_embed_res = await self._embedding_service.embed_texts_async(
                    texts=chunk_texts,
                    text_ids=chunk_ids,
                    batch_size=options.batch_size,
                )
            except EmbeddingException as exc:
                raise EmbeddingStageException(
                    document_id=document.id,
                    model_name=self._embedding_service.model_info.model_name,
                    reason=str(exc),
                ) from exc
            except Exception as exc:
                raise EmbeddingStageException(
                    document_id=document.id,
                    model_name=self._embedding_service.model_info.model_name,
                    reason=f"Unexpected embedding error: {exc}",
                ) from exc

            embedding_duration_ms = (time.perf_counter() - embed_start) * 1000.0

            logger.info(
                "ingestion_embeddings_completed",
                document_id=str(document.id),
                embedding_count=len(batch_embed_res.embeddings),
                model=self._embedding_service.model_info.model_name,
                duration_ms=round(embedding_duration_ms, 2),
            )

            await self._event_dispatcher.publish(
                EmbeddingsGenerated(
                    document_id=document.id,
                    embedding_count=len(batch_embed_res.embeddings),
                    dimension=self._embedding_service.dimension,
                    model_name=self._embedding_service.model_info.model_name,
                    duration_ms=embedding_duration_ms,
                )
            )

            # -----------------------------------------------------------------
            # 7. Vector Store Indexing (Qdrant)
            # -----------------------------------------------------------------
            current_stage = "vector_indexing"
            vec_start = time.perf_counter()

            # Ensure Qdrant collection is ready
            collection_name = self._settings.vectorstore.collection_name
            await self._vector_index_manager.ensure_collection_exists(
                collection_name=collection_name,
                vector_size=self._embedding_service.dimension,
            )

            # Assemble VectorRecords
            vector_records: list[VectorRecord] = []
            for chunk_obj, emb_vec in zip(
                chunk_result.chunks, batch_embed_res.embeddings, strict=True
            ):
                chunk_chk = (
                    chunk_obj.checksum
                    or hashlib.sha256(chunk_obj.text.encode("utf-8")).hexdigest()
                )
                payload = VectorPayload(
                    document_id=document.id,
                    chunk_id=chunk_obj.chunk_id,
                    chunk_index=chunk_obj.chunk_index,
                    text=chunk_obj.text,
                    file_name=document.original_filename,
                    title=document.title,
                    category=document.category.value
                    if hasattr(document.category, "value")
                    else str(document.category),
                    mime_type=document.mime_type,
                    checksum=chunk_chk,
                    page_number=chunk_obj.page_number,
                    heading=chunk_obj.section_title,
                    tags=document.tags or [],
                    language=document.language,
                    word_count=len(chunk_obj.text.split()),
                    token_count=chunk_obj.token_count,
                    character_count=chunk_obj.character_count,
                    created_by=document.uploaded_by,
                    indexed_at=datetime.now(UTC),
                )
                vector_records.append(
                    VectorRecord(
                        id=chunk_obj.chunk_id,
                        vector=emb_vec.vector,
                        payload=payload,
                    )
                )

            try:
                upserted_count = await self._vector_repository.upsert_vectors(
                    vector_records
                )
            except VectorStoreException as exc:
                raise VectorIndexingStageException(
                    document_id=document.id,
                    collection_name=collection_name,
                    reason=str(exc),
                ) from exc
            except Exception as exc:
                raise VectorIndexingStageException(
                    document_id=document.id,
                    collection_name=collection_name,
                    reason=f"Unexpected vector store error: {exc}",
                ) from exc

            vector_upload_duration_ms = (time.perf_counter() - vec_start) * 1000.0

            logger.info(
                "ingestion_vectors_indexed",
                document_id=str(document.id),
                vectors_stored=upserted_count,
                collection=collection_name,
                duration_ms=round(vector_upload_duration_ms, 2),
            )

            await self._event_dispatcher.publish(
                VectorsIndexed(
                    document_id=document.id,
                    vector_count=upserted_count,
                    collection_name=collection_name,
                    duration_ms=vector_upload_duration_ms,
                )
            )

            # -----------------------------------------------------------------
            # 8. Relational Chunk & Document Database Update
            # -----------------------------------------------------------------
            current_stage = "database_update"
            db_start = time.perf_counter()

            db_chunks: list[KnowledgeChunk] = []
            for chunk_obj in chunk_result.chunks:
                db_chunks.append(
                    KnowledgeChunk(
                        id=chunk_obj.chunk_id,
                        document_id=document.id,
                        chunk_index=chunk_obj.chunk_index,
                        text=chunk_obj.text,
                        page_number=chunk_obj.page_number,
                        heading=chunk_obj.section_title,
                        token_count=chunk_obj.token_count,
                        character_count=chunk_obj.character_count,
                        checksum=chunk_obj.checksum,
                    )
                )

            try:
                await chunk_repo.bulk_create(db_chunks)

                document.processing_status = ProcessingStatus.READY
                document.embedding_status = EmbeddingStatus.EMBEDDED
                document.language = proc_result.language or "en"
                document.updated_at = datetime.now(UTC)
                await session.commit()
            except Exception as exc:
                await session.rollback()
                raise DatabasePersistenceStageException(
                    document_id=document.id,
                    reason=f"Failed to persist chunk rows or update document status: {exc}",
                ) from exc

            database_duration_ms = (time.perf_counter() - db_start) * 1000.0

            # -----------------------------------------------------------------
            # 9. Completion & Telemetry Compilation
            # -----------------------------------------------------------------
            total_duration_ms = (time.perf_counter() - start_time) * 1000.0

            metrics = IngestionMetrics(
                total_duration_ms=round(total_duration_ms, 2),
                parsing_duration_ms=round(parsing_duration_ms, 2),
                cleaning_duration_ms=round(cleaning_duration_ms, 2),
                chunking_duration_ms=round(chunking_duration_ms, 2),
                embedding_duration_ms=round(embedding_duration_ms, 2),
                vector_upload_duration_ms=round(vector_upload_duration_ms, 2),
                database_duration_ms=round(database_duration_ms, 2),
            )

            report = IngestionReport(
                document_id=document.id,
                status=IngestionStatus.COMPLETED,
                original_filename=document.original_filename,
                file_size_bytes=document.file_size,
                character_count=proc_result.character_count,
                word_count=proc_result.word_count,
                token_count=chunk_result.total_tokens,
                total_chunks=chunk_result.total_chunks,
                total_vectors_stored=upserted_count,
                embedding_model=self._embedding_service.model_info.model_name,
                vector_dimension=self._embedding_service.dimension,
                collection_name=collection_name,
                metrics=metrics,
                errors=[],
                completed_at=datetime.now(UTC),
            )

            logger.info(
                "ingestion_pipeline_completed",
                document_id=str(document.id),
                total_chunks=report.total_chunks,
                total_vectors=report.total_vectors_stored,
                duration_ms=report.metrics.total_duration_ms,
            )

            await self._event_dispatcher.publish(
                IngestionCompleted(
                    document_id=document.id,
                    total_chunks=report.total_chunks,
                    total_vectors=report.total_vectors_stored,
                    total_tokens=report.token_count,
                    total_duration_ms=report.metrics.total_duration_ms,
                    report_summary=report.model_dump(),
                )
            )

            return report

        except Exception as exc:
            total_duration_ms = (time.perf_counter() - start_time) * 1000.0
            error_msg = str(exc)
            error_type = exc.__class__.__name__

            logger.error(
                "ingestion_pipeline_failed",
                document_id=str(document_id),
                stage=current_stage,
                error_type=error_type,
                error=error_msg,
                duration_ms=round(total_duration_ms, 2),
                exc_info=True,
            )

            # Safe database state rollback and transition to FAILED
            if document is not None:
                try:
                    await session.rollback()
                    document_ref = await session.get(KnowledgeDocument, document_id)
                    if document_ref is not None:
                        document_ref.processing_status = ProcessingStatus.FAILED
                        document_ref.embedding_status = EmbeddingStatus.FAILED
                        document_ref.updated_at = datetime.now(UTC)
                        await session.commit()
                except Exception as rollback_exc:
                    logger.error(
                        "ingestion_failure_status_update_error",
                        document_id=str(document_id),
                        error=str(rollback_exc),
                    )

            await self._event_dispatcher.publish(
                IngestionFailed(
                    document_id=document_id,
                    stage=current_stage,
                    error_type=error_type,
                    error_message=error_msg,
                    total_duration_ms=total_duration_ms,
                )
            )

            if isinstance(exc, IngestionPipelineException):
                raise exc

            raise IngestionPipelineException(
                message=f"Pipeline failed at stage '{current_stage}': {error_msg}",
                document_id=document_id,
                stage=current_stage,
                details={"error_type": error_type, "stage": current_stage},
            ) from exc

        finally:
            await self._release_document_lock(document_id, lock)

    async def ingest_content(
        self,
        content: bytes | Path,
        filename: str,
        user_id: uuid.UUID,
        session: AsyncSession,
        mime_type: str | None = None,
        title: str | None = None,
        category: str | None = None,
        options: IngestionOptions | None = None,
    ) -> IngestionReport:
        """Upload raw payload, register in KnowledgeDocument, and trigger ingestion."""
        raw_bytes = content if isinstance(content, bytes) else content.read_bytes()
        chk = hashlib.sha256(raw_bytes).hexdigest()
        file_ext = Path(filename).suffix.lower()

        # Store physical file
        if self._storage_service is not None:
            meta = await self._storage_service.store_file(
                filename=filename,
                content=raw_bytes,
                client_mime_type=mime_type,
            )
            stored_filename = meta.stored_filename
            storage_path = meta.storage_path
            chk = meta.checksum
            file_ext = meta.file_extension
            resolved_mime = meta.mime_type
            file_size = meta.file_size
        else:
            stored_filename = f"{uuid.uuid4().hex}{file_ext}"
            storage_path = stored_filename
            file_size = len(raw_bytes)
            resolved_mime = mime_type or "application/octet-stream"

        # Check if document with checksum already exists
        existing_stmt = select(KnowledgeDocument).where(
            KnowledgeDocument.checksum == chk,
            KnowledgeDocument.is_deleted.is_(False),
        )
        existing_res = await session.execute(existing_stmt)
        existing_doc = existing_res.scalar_one_or_none()

        if existing_doc is not None:
            if options and options.force_reindex:
                existing_doc.title = title or Path(filename).stem
                existing_doc.original_filename = filename
                existing_doc.stored_filename = stored_filename
                existing_doc.file_extension = file_ext
                existing_doc.mime_type = resolved_mime
                existing_doc.file_size = file_size
                existing_doc.storage_path = storage_path
                existing_doc.processing_status = ProcessingStatus.UPLOADED
                existing_doc.embedding_status = EmbeddingStatus.NOT_STARTED
                existing_doc.updated_at = datetime.now(UTC)
                await session.commit()
                return await self.ingest_document(
                    document_id=existing_doc.id, session=session, options=options
                )
            elif existing_doc.processing_status in (
                ProcessingStatus.FAILED,
                ProcessingStatus.UPLOADED,
            ):
                existing_doc.title = title or existing_doc.title
                existing_doc.stored_filename = stored_filename
                existing_doc.storage_path = storage_path
                existing_doc.file_size = file_size
                existing_doc.processing_status = ProcessingStatus.UPLOADED
                existing_doc.embedding_status = EmbeddingStatus.NOT_STARTED
                existing_doc.updated_at = datetime.now(UTC)
                await session.commit()
                return await self.ingest_document(
                    document_id=existing_doc.id, session=session, options=options
                )
            elif (
                existing_doc.processing_status == ProcessingStatus.READY
                and existing_doc.embedding_status == EmbeddingStatus.EMBEDDED
            ):
                logger.info(
                    "document_already_indexed_skipping",
                    document_id=str(existing_doc.id),
                    checksum=chk,
                    filename=filename,
                )
                return IngestionReport(
                    document_id=existing_doc.id,
                    status=IngestionStatus.COMPLETED,
                    original_filename=existing_doc.original_filename,
                    file_size_bytes=existing_doc.file_size,
                    character_count=0,
                    word_count=0,
                    token_count=0,
                    total_chunks=0,
                    total_vectors_stored=0,
                    embedding_model=self._embedding_service.model_info.model_name,
                    vector_dimension=self._embedding_service.dimension,
                    collection_name=self._settings.vectorstore.collection_name,
                    metrics=IngestionMetrics(
                        total_duration_ms=0.0,
                        parsing_duration_ms=0.0,
                        cleaning_duration_ms=0.0,
                        chunking_duration_ms=0.0,
                        embedding_duration_ms=0.0,
                        vector_upload_duration_ms=0.0,
                        database_duration_ms=0.0,
                    ),
                    errors=[],
                    completed_at=datetime.now(UTC),
                )
            else:
                return await self.ingest_document(
                    document_id=existing_doc.id, session=session, options=options
                )

        # Create new database record
        doc = KnowledgeDocument(
            title=title or Path(filename).stem,
            original_filename=filename,
            stored_filename=stored_filename,
            file_extension=file_ext,
            mime_type=resolved_mime,
            file_size=file_size,
            checksum=chk,
            storage_path=storage_path,
            uploaded_by=user_id,
            processing_status=ProcessingStatus.UPLOADED,
            embedding_status=EmbeddingStatus.NOT_STARTED,
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)

        return await self.ingest_document(
            document_id=doc.id, session=session, options=options
        )
