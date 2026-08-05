"""BM25 Sparse Lexical Retrieval Strategy and Inverted Index.

Implements Okapi BM25 ranking algorithm with Robertson-Spärck Jones non-negative IDF,
document length normalization, in-memory inverted index, and filter matching.
"""

from __future__ import annotations

import math
import time
from collections import Counter
from typing import Any

from app.core.logging import get_logger
from app.retrieval.exceptions import SparseRetrievalException
from app.retrieval.models import CandidateChunk, SearchFilters, SearchOptions
from app.retrieval.query_preprocessor import TOKEN_REGEX
from app.retrieval.strategies import RetrievalStrategy

logger = get_logger(__name__)


class IndexedDocument:
    """Internal representation of a document chunk in the BM25 index."""

    __slots__ = (
        "category",
        "chunk_id",
        "chunk_index",
        "doc_length",
        "document_id",
        "file_name",
        "heading",
        "metadata",
        "page_number",
        "tags",
        "term_frequencies",
        "text",
        "title",
    )

    def __init__(
        self,
        chunk_id: str,
        document_id: str,
        text: str,
        tokens: list[str],
        chunk_index: int = 0,
        heading: str | None = None,
        page_number: int | None = None,
        title: str | None = None,
        file_name: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.chunk_index = chunk_index
        self.text = text
        self.term_frequencies: dict[str, int] = dict(Counter(tokens))
        self.doc_length = len(tokens)
        self.heading = heading
        self.page_number = page_number
        self.title = title
        self.file_name = file_name
        self.category = category
        self.tags = tags or []
        self.metadata = metadata or {}


class BM25Index:
    """In-memory Inverted Index and Okapi BM25 Scoring Engine.

    Implements the standard Okapi BM25 formula with Robertson-Spärck Jones positive
    inverse document frequency computation.
    """

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        epsilon: float = 0.25,
    ) -> None:
        """Initialize BM25Index.

        Args:
            k1: Term frequency saturation parameter (typically 1.2 to 2.0).
            b: Document length normalization parameter (0.0 to 1.0).
            epsilon: Minimum IDF floor threshold.
        """
        self.k1 = k1
        self.b = b
        self.epsilon = epsilon

        self._documents: list[IndexedDocument] = []
        self._doc_map: dict[str, int] = {}  # chunk_id -> index in _documents
        # term -> list of (doc_index, term_frequency)
        self._inverted_index: dict[str, list[tuple[int, int]]] = {}
        # term -> document frequency (number of documents containing term)
        self._df: dict[str, int] = {}
        self._idf_cache: dict[str, float] = {}
        self._total_doc_length = 0
        self._avg_doc_length = 0.0

    @property
    def total_documents(self) -> int:
        """Total number of indexed documents."""
        return len(self._documents)

    def add_document(
        self,
        chunk_id: str,
        document_id: str,
        text: str,
        chunk_index: int = 0,
        heading: str | None = None,
        page_number: int | None = None,
        title: str | None = None,
        file_name: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Tokenize and add a document chunk to the BM25 index."""
        raw_tokens = TOKEN_REGEX.findall(text.lower())
        tokens = [t.strip("-_") for t in raw_tokens if len(t.strip("-_")) > 1]
        if not tokens:
            tokens = [t for t in raw_tokens if t]

        doc_idx = len(self._documents)
        doc = IndexedDocument(
            chunk_id=chunk_id,
            document_id=document_id,
            text=text,
            tokens=tokens,
            chunk_index=chunk_index,
            heading=heading,
            page_number=page_number,
            title=title,
            file_name=file_name,
            category=category,
            tags=tags,
            metadata=metadata,
        )
        self._documents.append(doc)
        self._doc_map[chunk_id] = doc_idx

        # Update inverted index and DF
        for term, freq in doc.term_frequencies.items():
            if term not in self._inverted_index:
                self._inverted_index[term] = []
                self._df[term] = 0
            self._inverted_index[term].append((doc_idx, freq))
            self._df[term] += 1

        self._total_doc_length += doc.doc_length
        self._avg_doc_length = self._total_doc_length / len(self._documents)
        # Clear IDF cache when corpus changes
        self._idf_cache.clear()

    def add_documents_batch(self, docs_data: list[dict[str, Any]]) -> int:
        """Batch index multiple chunk dictionaries."""
        count = 0
        for item in docs_data:
            self.add_document(
                chunk_id=str(item["chunk_id"]),
                document_id=str(item["document_id"]),
                text=item["text"],
                chunk_index=int(item.get("chunk_index") or 0),
                heading=item.get("heading"),
                page_number=item.get("page_number"),
                title=item.get("title"),
                file_name=item.get("file_name"),
                category=item.get("category"),
                tags=item.get("tags"),
                metadata=item.get("metadata"),
            )
            count += 1
        return count

    def _compute_idf(self, term: str) -> float:
        """Compute Robertson-Spärck Jones IDF with smoothed positive floor."""
        if term in self._idf_cache:
            return self._idf_cache[term]

        df = self._df.get(term, 0)
        if df == 0:
            return 0.0

        n = len(self._documents)
        # Formula: ln(1 + (N - df + 0.5) / (df + 0.5)) ensures >= 0
        idf = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
        if idf < self.epsilon:
            idf = self.epsilon

        self._idf_cache[term] = idf
        return idf

    def search(
        self,
        tokens: list[str],
        limit: int = 50,
        filters: SearchFilters | None = None,
    ) -> list[tuple[IndexedDocument, float]]:
        """Score indexed documents against query tokens using BM25.

        Args:
            tokens: Query tokens.
            limit: Maximum candidate documents to return.
            filters: Structured filters to restrict candidate matching.

        Returns:
            list[tuple[IndexedDocument, float]]: Ranked (document, score) tuples.
        """
        if not tokens or not self._documents:
            return []

        doc_scores: dict[int, float] = {}
        avgdl = self._avg_doc_length or 1.0

        for term in set(tokens):
            if term not in self._inverted_index:
                continue

            idf = self._compute_idf(term)
            for doc_idx, tf in self._inverted_index[term]:
                doc = self._documents[doc_idx]

                # If filters active, verify document satisfies filters
                if filters and not filters.is_empty():
                    # Combine doc attributes + metadata
                    payload = dict(doc.metadata)
                    payload["chunk_id"] = doc.chunk_id
                    payload["document_id"] = doc.document_id
                    payload["category"] = doc.category
                    payload["tags"] = doc.tags
                    if not filters.matches_dict(payload):
                        continue

                # BM25 term score component
                len_norm = 1.0 - self.b + self.b * (doc.doc_length / avgdl)
                tf_component = (tf * (self.k1 + 1.0)) / (tf + self.k1 * len_norm)
                score_increment = idf * tf_component

                doc_scores[doc_idx] = doc_scores.get(doc_idx, 0.0) + score_increment

        if not doc_scores:
            return []

        # Sort descending by BM25 score
        sorted_pairs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        top_pairs = sorted_pairs[:limit]

        return [(self._documents[idx], round(score, 6)) for idx, score in top_pairs]


class BM25RetrievalStrategy(RetrievalStrategy):
    """Retrieves document chunks based on BM25 lexical term frequency scoring."""

    def __init__(
        self,
        index: BM25Index | None = None,
        k1: float = 1.5,
        b: float = 0.75,
        epsilon: float = 0.25,
    ) -> None:
        """Initialize BM25RetrievalStrategy.

        Args:
            index: Pre-populated or shared BM25Index instance.
            k1: BM25 k1 parameter.
            b: BM25 b parameter.
            epsilon: Minimum IDF parameter.
        """
        self._index = index or BM25Index(k1=k1, b=b, epsilon=epsilon)

    @property
    def name(self) -> str:
        return "bm25"

    @property
    def index(self) -> BM25Index:
        """Access underlying BM25 inverted index."""
        return self._index

    async def retrieve(
        self,
        query: str,
        normalized_query: str,
        tokens: list[str],
        options: SearchOptions,
        filters: SearchFilters | None = None,
    ) -> list[CandidateChunk]:
        """Execute BM25 lexical search against the inverted index."""
        start_time = time.perf_counter()
        try:
            results = self._index.search(
                tokens=tokens,
                limit=options.sparse_candidate_limit,
                filters=filters,
            )

            candidates: list[CandidateChunk] = []
            for rank, (doc, score) in enumerate(results, start=1):
                cand = CandidateChunk(
                    chunk_id=doc.chunk_id,
                    document_id=doc.document_id,
                    chunk_index=doc.chunk_index,
                    text=doc.text,
                    score=score,
                    rank=rank,
                    strategy_name=self.name,
                    heading=doc.heading,
                    page_number=doc.page_number,
                    title=doc.title,
                    file_name=doc.file_name,
                    category=doc.category,
                    tags=doc.tags,
                    metadata=doc.metadata,
                )
                candidates.append(cand)

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.info(
                "bm25_retrieval_completed",
                tokens_count=len(tokens),
                candidates_found=len(candidates),
                latency_ms=round(elapsed_ms, 2),
            )
            return candidates

        except Exception as exc:
            logger.error("bm25_retrieval_failed", error=str(exc))
            raise SparseRetrievalException(reason=str(exc)) from exc
