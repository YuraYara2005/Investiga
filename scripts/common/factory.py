"""Dependency Injection Factory for Investiga CLI.

Assembles and wires existing backend subsystems (ETL, Storage, Document Processing,
Chunking, Embeddings, Vector Store, Retrieval, RAG, Evaluation) into operational services.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.common.helpers import bootstrap_environment

bootstrap_environment()

# pyrefly: ignore [missing-import]
from app.core.config import Settings, get_settings
# pyrefly: ignore [missing-import]
from app.core.logging import get_logger
# pyrefly: ignore [missing-import]
from app.db.session import get_standalone_session
# pyrefly: ignore [missing-import]
from app.embeddings.embedding_service import (
    EmbeddingService,
    create_embedding_service,
)
# pyrefly: ignore [missing-import]
from app.embeddings.models import EmbeddingModelInfo
# pyrefly: ignore [missing-import]
from app.embeddings.provider import EmbeddingProvider
# pyrefly: ignore [missing-import]
from app.etl.pipeline import ETLPipeline
# pyrefly: ignore [missing-import]
from app.etl.registry import LoaderRegistry, get_loader_registry
# pyrefly: ignore [missing-import]
from app.etl.service import ETLService
# pyrefly: ignore [missing-import]
from app.evaluation.benchmark import RAGBenchmark
# pyrefly: ignore [missing-import]
from app.evaluation.evaluator import RAGEvaluator
# pyrefly: ignore [missing-import]
from app.ingestion.pipeline import DocumentIngestionPipeline
# pyrefly: ignore [missing-import]
from app.rag.providers.base import LLMProviderRegistry
# pyrefly: ignore [missing-import]
from app.rag.providers.gemini import GeminiLLMProvider
# pyrefly: ignore [missing-import]
from app.rag.providers.mock import MockLLMProvider
# pyrefly: ignore [missing-import]
from app.rag.providers.ollama import OllamaLLMProvider
# pyrefly: ignore [missing-import]
from app.rag.service import RAGService, create_rag_service
from app.retrieval.bm25 import BM25Index
# pyrefly: ignore [missing-import]
from app.retrieval.retriever import HybridRetriever
# pyrefly: ignore [missing-import]
from app.retrieval.service import RetrievalService, create_retrieval_service
# pyrefly: ignore [missing-import]
from app.vectorstore.qdrant_provider import QdrantProvider
# pyrefly: ignore [missing-import]
from app.vectorstore.vector_repository import VectorRepository
from sqlalchemy.ext.asyncio import AsyncSession


logger = get_logger(__name__)


def get_cli_settings() -> Settings:
    """Retrieve application configuration settings."""
    return get_settings()


@asynccontextmanager
async def get_cli_db_session(settings: Settings | None = None) -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated standalone asynchronous database session."""
    async with get_standalone_session() as session:
        yield session



class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic offline embedding provider for resilient CLI execution."""

    def __init__(self, dimension: int = 768, model_name: str = "mock-bge-base-en") -> None:
        self._dimension = dimension
        self._model_name = model_name

    @property
    def model_info(self) -> EmbeddingModelInfo:
        return EmbeddingModelInfo(
            model_name=self._model_name,
            provider="MockEmbeddingProvider",
            dimension=self._dimension,
            device="cpu",
            max_seq_length=512,
            normalize_embeddings=True,
        )

    def encode_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
        normalize: bool = True,
        show_progress: bool = False,
    ) -> np.ndarray:
        import hashlib
        vectors = []
        for text in texts:
            h = hashlib.sha256(text.encode("utf-8")).digest()
            rng = np.random.default_rng(int.from_bytes(h[:8], "big"))
            vec = rng.standard_normal(self._dimension).astype(np.float32)
            if normalize:
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
            vectors.append(vec)
        return np.array(vectors, dtype=np.float32)


def create_cli_embedding_service(
    settings: Settings | None = None,
    auto_load: bool = True,
) -> EmbeddingService:
    """Instantiate EmbeddingService using configured model, falling back to mock provider if offline."""
    import os

    root_settings = settings or get_cli_settings()
    if os.getenv("INVESTIGA_OFFLINE", "").lower() in ("1", "true") or os.getenv("INVESTIGA_MOCK_EMBEDDINGS", "").lower() in ("1", "true"):
        mock_provider = MockEmbeddingProvider(dimension=root_settings.embeddings.dimension)
        return EmbeddingService(
            provider=mock_provider,
            default_batch_size=root_settings.embeddings.batch_size,
            normalize=root_settings.embeddings.normalize_embeddings,
        )

    try:
        return create_embedding_service(
            model_name=root_settings.embeddings.model_name,
            device=root_settings.embeddings.device,
            normalize=root_settings.embeddings.normalize_embeddings,
            batch_size=root_settings.embeddings.batch_size,
            auto_load=auto_load,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "embedding_provider_fallback",
            model=root_settings.embeddings.model_name,
            reason=str(exc),
        )
        mock_provider = MockEmbeddingProvider(dimension=root_settings.embeddings.dimension)
        return EmbeddingService(
            provider=mock_provider,
            default_batch_size=root_settings.embeddings.batch_size,
            normalize=root_settings.embeddings.normalize_embeddings,
        )


def create_cli_vector_repository(
    settings: Settings | None = None,
) -> VectorRepository:
    """Instantiate VectorRepository backed by QdrantProvider."""
    root_settings = settings or get_cli_settings()
    qdrant_provider = QdrantProvider(settings=root_settings.vectorstore)
    return VectorRepository(
        provider=qdrant_provider,
        settings=root_settings.vectorstore,
    )


async def build_cli_bm25_index_async(
    settings: Settings | None = None,
) -> BM25Index:
    """Build and populate a BM25Index from PostgreSQL knowledge chunks."""
    root_settings = settings or get_cli_settings()
    try:
        async with get_cli_db_session(root_settings) as session:
            index = await BM25Index.from_async_session(
                session=session,
                k1=root_settings.retrieval.bm25_k1,
                b=root_settings.retrieval.bm25_b,
                epsilon=root_settings.retrieval.bm25_epsilon,
            )
            logger.info("cli_bm25_index_loaded", documents_count=index.total_documents)
            return index
    except Exception as exc:
        logger.warning("cli_bm25_index_load_failed", error=str(exc))
        return BM25Index(
            k1=root_settings.retrieval.bm25_k1,
            b=root_settings.retrieval.bm25_b,
            epsilon=root_settings.retrieval.bm25_epsilon,
        )


def create_cli_retrieval_service(
    settings: Settings | None = None,
    embedding_service: EmbeddingService | None = None,
    vector_repository: VectorRepository | None = None,
    bm25_index: BM25Index | None = None,
) -> RetrievalService:
    """Instantiate Hybrid RetrievalService with Dense and Sparse strategies."""
    root_settings = settings or get_cli_settings()
    emb_svc = embedding_service or create_cli_embedding_service(settings=root_settings)
    vec_repo = vector_repository or create_cli_vector_repository(settings=root_settings)

    return create_retrieval_service(
        embedding_service=emb_svc,
        vector_repository=vec_repo,
        bm25_index=bm25_index,
        settings=root_settings,
    )



def create_cli_rag_service(
    settings: Settings | None = None,
    retrieval_service: RetrievalService | None = None,
    custom_registry: LLMProviderRegistry | None = None,
) -> RAGService:
    """Instantiate complete RAGService with all configured LLM providers."""
    root_settings = settings or get_cli_settings()
    ret_svc = retrieval_service or create_cli_retrieval_service(settings=root_settings)
    retriever: HybridRetriever = ret_svc.retriever

    registry = custom_registry or LLMProviderRegistry()
    if custom_registry is None:
        registry.register(GeminiLLMProvider(settings=root_settings.rag))
        registry.register(OllamaLLMProvider(settings=root_settings.rag))
        registry.register(MockLLMProvider())

    return create_rag_service(
        retriever=retriever,
        settings=root_settings.rag,
        custom_registry=registry,
    )


def create_cli_evaluator(
    rag_service: RAGService | None = None,
    settings: Settings | None = None,
) -> RAGEvaluator:
    """Instantiate RAGEvaluator wrapping RAGService."""
    rag_svc = rag_service or create_cli_rag_service(settings=settings)
    return RAGEvaluator(rag_service=rag_svc)


def create_cli_benchmark(
    evaluator: RAGEvaluator | None = None,
    providers: list[str] | None = None,
    weights: dict[str, float] | None = None,
    settings: Settings | None = None,
) -> RAGBenchmark:
    """Instantiate RAGBenchmark for multi-provider comparison."""
    ev = evaluator or create_cli_evaluator(settings=settings)
    return RAGBenchmark(
        evaluator=ev,
        providers=providers or ["mock", "gemini", "ollama"],
        weights=weights,
    )


def create_cli_etl_service(
    loader_registry: LoaderRegistry | None = None,
    ingestion_pipeline: DocumentIngestionPipeline | None = None,
) -> ETLService:
    """Instantiate ETLService coordinating loaders and IngestionPipeline."""
    registry = loader_registry or get_loader_registry()
    pipeline = ETLPipeline(
        loader_registry=registry,
        ingestion_pipeline=ingestion_pipeline or DocumentIngestionPipeline(),
    )
    return ETLService(
        pipeline=pipeline,
        loader_registry=registry,
    )
