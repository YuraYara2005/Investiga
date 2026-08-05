"""Document Ingestion and Vectorization Subsystem for Investiga.

Provides the end-to-end orchestration pipeline connecting Storage, Parsing,
Text Cleaning, Intelligent Chunking, Embedding Generation, Qdrant Vector Persistence,
and Relational Database updates.
"""

from app.ingestion.exceptions import (
    DatabasePersistenceStageException,
    DocumentAlreadyProcessingException,
    DocumentChunkingStageException,
    DocumentNotEligibleException,
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
from app.ingestion.pipeline import DocumentIngestionPipeline
from app.ingestion.service import IngestionService

__all__ = [
    "DatabasePersistenceStageException",
    "DocumentAlreadyProcessingException",
    "DocumentChunkingStageException",
    "DocumentIngestionPipeline",
    "DocumentIngestionPipelineInterface",
    "DocumentNotEligibleException",
    "DocumentNotFoundException",
    "DocumentParsingStageException",
    "EmbeddingStageException",
    "IngestionMetrics",
    "IngestionOptions",
    "IngestionPipelineException",
    "IngestionReport",
    "IngestionService",
    "IngestionStatus",
    "StorageReadException",
    "VectorIndexingStageException",
]
