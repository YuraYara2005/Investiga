"""Enterprise Hybrid Retrieval Orchestrator.

Orchestrates query preprocessing, concurrent retrieval across multiple strategies
(Dense, BM25, Graph, etc.), partial failure fault-tolerance, pluggable rank fusion,
lightweight caching, and observability tracing.
"""

from __future__ import annotations

import asyncio
import time

from app.core.config import RetrievalSettings
from app.core.logging import get_logger
from app.retrieval.cache import InMemoryRetrievalCache, RetrievalCache
from app.retrieval.exceptions import (
    RetrievalCancelledException,
    RetrievalException,
    RetrievalTimeoutException,
)
from app.retrieval.fusion import FusionEngine, FusionStrategy
from app.retrieval.models import (
    CandidateChunk,
    RetrievalMetrics,
    RetrievalResult,
    RetrievalTrace,
    SearchFilters,
    SearchOptions,
    SearchQuery,
)
from app.retrieval.query_preprocessor import QueryPreprocessor
from app.retrieval.strategies import RetrievalStrategy, StrategyRegistry

logger = get_logger(__name__)


class HybridRetriever:
    """Enterprise hybrid retrieval engine.

    Orchestrates multiple independent RetrievalStrategy implementations concurrently,
    resiliently combines their ranked candidates using a pluggable FusionStrategy,
    and returns deduplicated, highly-relevant knowledge chunks.
    """

    def __init__(
        self,
        strategy_registry: StrategyRegistry | None = None,
        fusion_engine: FusionEngine | None = None,
        query_preprocessor: QueryPreprocessor | None = None,
        cache: RetrievalCache | None = None,
        settings: RetrievalSettings | None = None,
    ) -> None:
        """Initialize HybridRetriever.

        Args:
            strategy_registry: Registry containing available retrieval strategies.
            fusion_engine: Pluggable fusion algorithm registry.
            query_preprocessor: Sanitizer and token extractor.
            cache: Cache provider for query and candidate acceleration.
            settings: Configuration settings for retrieval pipeline.
        """
        self._settings = settings or RetrievalSettings()
        self._strategies = strategy_registry or StrategyRegistry()
        self._fusion_engine = fusion_engine or FusionEngine()
        self._preprocessor = query_preprocessor or QueryPreprocessor(
            max_query_length=self._settings.max_query_length
        )
        self._cache = (
            cache
            if cache is not None
            else (
                InMemoryRetrievalCache(
                    default_ttl_seconds=self._settings.cache_ttl_seconds,
                    max_size=self._settings.cache_max_size,
                )
                if self._settings.enable_cache
                else None
            )
        )

    def register_strategy(self, strategy: RetrievalStrategy) -> None:
        """Register a retrieval strategy."""
        self._strategies.register(strategy)

    def register_fusion(self, strategy: FusionStrategy) -> None:
        """Register a fusion strategy."""
        self._fusion_engine.register(strategy)

    def _resolve_options(self, options: SearchOptions | None) -> SearchOptions:
        """Merge provided runtime options with application settings defaults."""
        if options is None:
            return SearchOptions(
                top_k=self._settings.top_k,
                dense_candidate_limit=self._settings.dense_candidate_limit,
                sparse_candidate_limit=self._settings.sparse_candidate_limit,
                dense_weight=self._settings.dense_weight,
                sparse_weight=self._settings.sparse_weight,
                rrf_k=self._settings.rrf_k,
                min_score_threshold=self._settings.min_score_threshold,
                enabled_dense=self._settings.enabled_dense,
                enabled_sparse=self._settings.enabled_sparse,
                fusion_strategy=self._settings.fusion_strategy,
                enable_cache=self._settings.enable_cache,
                timeout_seconds=self._settings.timeout_seconds,
            )
        return options

    async def search(
        self,
        query: str | SearchQuery,
        options: SearchOptions | None = None,
        filters: SearchFilters | None = None,
    ) -> RetrievalResult:
        """Execute hybrid multi-strategy retrieval and rank fusion.

        Args:
            query: Raw query string or SearchQuery object.
            options: Optional runtime execution parameters.
            filters: Optional structured metadata filters.

        Returns:
            RetrievalResult: Complete ranked chunks, metrics, applied filters, and trace.

        Raises:
            InvalidQueryException: If query is empty or invalid.
            RetrievalTimeoutException: If execution exceeds configured timeout.
            RetrievalException: If all retrieval strategies fail.
        """
        overall_start = time.perf_counter()

        # 1. Unpack query, filters, and options
        raw_query: str
        if isinstance(query, SearchQuery):
            raw_query = query.query
            filters = query.filters if filters is None else filters
            options = query.options if options is None else options
        else:
            raw_query = query

        resolved_options = self._resolve_options(options)

        # 2. Preprocess & validate query
        prep_start = time.perf_counter()
        normalized_query, tokens = self._preprocessor.preprocess(raw_query)
        prep_duration_ms = (time.perf_counter() - prep_start) * 1000.0

        # 3. Check Cache
        cache_key: str | None = None
        if resolved_options.enable_cache and self._cache is not None:
            cache_key = RetrievalCache.build_cache_key(
                normalized_query=normalized_query,
                filters=filters,
                options=resolved_options,
            )
            cached_result: RetrievalResult | None = await self._cache.get(cache_key)
            if cached_result is not None:
                logger.info("retrieval_cache_hit", query=normalized_query)
                # Create a fresh copy with updated trace showing cache hit
                cached_trace = cached_result.trace
                if cached_trace:
                    updated_trace = cached_trace.model_copy(update={"cache_hit": True})
                else:
                    updated_trace = None
                return cached_result.model_copy(update={"trace": updated_trace})

        # 4. Determine active strategies to run
        active_strategy_names: list[str] = []
        if (
            resolved_options.enabled_dense
            and "dense" in self._strategies.list_strategies()
        ):
            active_strategy_names.append("dense")
        if (
            resolved_options.enabled_sparse
            and "bm25" in self._strategies.list_strategies()
        ):
            active_strategy_names.append("bm25")

        # Fallback to any other registered strategies if explicitly present
        for strat_name in self._strategies.list_strategies():
            if (
                strat_name not in ("dense", "bm25")
                and strat_name not in active_strategy_names
            ):
                active_strategy_names.append(strat_name)

        if not active_strategy_names:
            raise RetrievalException(
                message="No retrieval strategies are enabled or registered."
            )

        logger.info(
            "hybrid_retrieval_started",
            query=normalized_query,
            active_strategies=active_strategy_names,
            top_k=resolved_options.top_k,
        )

        # 5. Concurrently execute all active strategies with timeout
        async def _run_strategy(
            strat_name: str,
        ) -> tuple[str, list[CandidateChunk], float]:
            s_start = time.perf_counter()
            strat = self._strategies.get(strat_name)
            candidates = await strat.retrieve(
                query=raw_query,
                normalized_query=normalized_query,
                tokens=tokens,
                options=resolved_options,
                filters=filters,
            )
            s_lat = (time.perf_counter() - s_start) * 1000.0
            return strat_name, candidates, s_lat

        tasks = [_run_strategy(name) for name in active_strategy_names]

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=resolved_options.timeout_seconds,
            )
        except TimeoutError as exc:
            raise RetrievalTimeoutException(
                timeout_seconds=resolved_options.timeout_seconds
            ) from exc
        except asyncio.CancelledError as exc:
            raise RetrievalCancelledException() from exc

        # 6. Process results & isolate partial failures
        strategy_candidates: dict[str, list[CandidateChunk]] = {}
        strategy_latencies: dict[str, float] = {}
        failure_reasons: list[str] = []
        partial_failure = False

        for i, res in enumerate(results):
            strat_name = active_strategy_names[i]
            if isinstance(res, BaseException):
                partial_failure = True
                failure_msg = f"Strategy '{strat_name}' failed: {res}"
                failure_reasons.append(failure_msg)
                logger.warning(
                    "strategy_execution_failed", strategy=strat_name, error=str(res)
                )
            else:
                s_name, cands, s_lat = res
                strategy_candidates[s_name] = cands
                strategy_latencies[s_name] = round(s_lat, 2)

        # If ALL strategies failed, raise error
        if not strategy_candidates:
            raise RetrievalException(
                message=f"All retrieval strategies failed: {'; '.join(failure_reasons)}"
            )

        # 7. Pluggable Rank Fusion
        fusion_start = time.perf_counter()
        fusion_impl = self._fusion_engine.get(resolved_options.fusion_strategy)
        fused_chunks = fusion_impl.fuse(strategy_candidates, resolved_options)
        fusion_duration_ms = (time.perf_counter() - fusion_start) * 1000.0

        total_duration_ms = (time.perf_counter() - overall_start) * 1000.0

        # 8. Compute telemetry & metrics
        dense_candidates = strategy_candidates.get("dense", [])
        sparse_candidates = strategy_candidates.get("bm25", [])
        all_candidate_ids = {
            c.chunk_id_str for cands in strategy_candidates.values() for c in cands
        }

        top_score = fused_chunks[0].score if fused_chunks else 0.0
        avg_score = (
            sum(c.score for c in fused_chunks) / len(fused_chunks)
            if fused_chunks
            else 0.0
        )

        metrics = RetrievalMetrics(
            query_prep_duration_ms=round(prep_duration_ms, 2),
            embedding_duration_ms=round(strategy_latencies.get("dense", 0.0), 2),
            dense_search_duration_ms=round(strategy_latencies.get("dense", 0.0), 2),
            sparse_search_duration_ms=round(strategy_latencies.get("bm25", 0.0), 2),
            fusion_duration_ms=round(fusion_duration_ms, 2),
            total_duration_ms=round(total_duration_ms, 2),
            dense_candidates_count=len(dense_candidates),
            sparse_candidates_count=len(sparse_candidates),
            fused_candidates_count=len(all_candidate_ids),
            returned_chunks_count=len(fused_chunks),
            top_score=round(top_score, 4),
            average_score=round(avg_score, 4),
        )

        all_sources = sorted(
            {src for chunk in fused_chunks for src in chunk.retrieval_sources}
        )

        # Determine embedding model name if dense strategy was run
        dense_strat = (
            self._strategies.get("dense")
            if "dense" in self._strategies.list_strategies()
            else None
        )
        embed_model = getattr(dense_strat, "embedding_model_name", "none")

        trace = RetrievalTrace(
            query=raw_query,
            normalized_query=normalized_query,
            embedding_model=embed_model,
            retrieval_strategies=active_strategy_names,
            fusion_strategy=resolved_options.fusion_strategy,
            dense_candidates=len(dense_candidates),
            sparse_candidates=len(sparse_candidates),
            returned_chunks=len(fused_chunks),
            latencies={
                "prep": round(prep_duration_ms, 2),
                **strategy_latencies,
                "fusion": round(fusion_duration_ms, 2),
                "total": round(total_duration_ms, 2),
            },
            cache_hit=False,
            partial_failure=partial_failure,
            failure_reasons=failure_reasons,
            retrieval_sources=all_sources,
        )

        retrieval_result = RetrievalResult(
            query=raw_query,
            normalized_query=normalized_query,
            chunks=fused_chunks,
            total_found=len(all_candidate_ids),
            applied_filters=filters.model_dump(mode="json") if filters else {},
            metrics=metrics,
            trace=trace,
        )

        # 9. Store in cache if enabled
        if (
            resolved_options.enable_cache
            and self._cache is not None
            and cache_key is not None
        ):
            await self._cache.set(
                key=cache_key,
                value=retrieval_result,
                ttl_seconds=self._settings.cache_ttl_seconds,
            )

        logger.info(
            "hybrid_retrieval_completed",
            returned_chunks=len(fused_chunks),
            total_duration_ms=round(total_duration_ms, 2),
            top_score=round(top_score, 4),
            partial_failure=partial_failure,
        )

        return retrieval_result
