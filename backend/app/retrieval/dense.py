"""Dense Vector Retrieval Strategy.

Implements RetrievalStrategy by embedding query strings with the EmbeddingService
and querying nearest neighbors via the VectorRepository against Qdrant vector indices.
"""

from __future__ import annotations

import time

from app.core.logging import get_logger
from app.embeddings.embedding_service import EmbeddingService
from app.retrieval.exceptions import DenseRetrievalException
from app.retrieval.models import CandidateChunk, SearchFilters, SearchOptions
from app.retrieval.strategies import RetrievalStrategy
from app.vectorstore.vector_repository import VectorRepository

logger = get_logger(__name__)


class DenseRetrievalStrategy(RetrievalStrategy):
    """Retrieves semantically similar document chunks via dense vector embeddings."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_repository: VectorRepository,
    ) -> None:
        """Initialize DenseRetrievalStrategy.

        Args:
            embedding_service: Model inference service for vector generation.
            vector_repository: Vector database abstraction layer.
        """
        self._embedding_service = embedding_service
        self._vector_repository = vector_repository

    @property
    def name(self) -> str:
        return "dense"

    @property
    def embedding_model_name(self) -> str:
        """Name of the active embedding model."""
        return self._embedding_service.model_info.model_name

    async def retrieve(
        self,
        query: str,
        normalized_query: str,
        tokens: list[str],
        options: SearchOptions,
        filters: SearchFilters | None = None,
    ) -> list[CandidateChunk]:
        """Generate query embedding and retrieve nearest neighbors from vector store."""
        start_time = time.perf_counter()
        try:
            # 1. Embed normalized query
            embed_vector = await self._embedding_service.embed_text_async(
                text=normalized_query
            )

            # 2. Build metadata filter if active
            filter_builder = None
            if filters and not filters.is_empty():
                filter_builder = filters.to_filter_builder()

            # 3. Query vector store
            search_result = await self._vector_repository.search(
                query_vector=embed_vector.vector,
                limit=options.dense_candidate_limit,
                filter_builder=filter_builder,
                collection_name=options.collection_name,
            )

            # 4. Map ScoredVectorRecords to CandidateChunks
            candidates: list[CandidateChunk] = []
            for idx, rec in enumerate(search_result.results):
                p = rec.payload_dict
                chunk_id = p.get("chunk_id") or str(rec.id)
                doc_id = p.get("document_id") or str(rec.id)
                chunk_text = (
                    p.get("raw_text") or p.get("normalized_text") or p.get("text") or ""
                )

                candidate = CandidateChunk(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    chunk_index=int(p.get("chunk_index") or 0),
                    text=chunk_text,
                    score=float(rec.score),
                    rank=idx + 1,
                    strategy_name=self.name,
                    heading=p.get("heading"),
                    page_number=p.get("page_number"),
                    title=p.get("title"),
                    file_name=p.get("file_name"),
                    category=p.get("category"),
                    tags=p.get("tags") or [],
                    metadata=p,
                )
                candidates.append(candidate)

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.info(
                "dense_retrieval_completed",
                candidates_found=len(candidates),
                latency_ms=round(elapsed_ms, 2),
                collection_name=options.collection_name
                or self._vector_repository.default_collection_name,
            )
            return candidates

        except Exception as exc:
            logger.error("dense_retrieval_failed", error=str(exc))
            raise DenseRetrievalException(
                reason=str(exc),
                collection_name=options.collection_name,
            ) from exc
