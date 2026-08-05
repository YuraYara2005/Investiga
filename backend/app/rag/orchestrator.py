"""Enterprise RAG Pipeline Orchestrator.

Coordinates Hybrid Retrieval, Guardrail Verification, Context Building,
Prompt Strategy Resolution, LLM Provider Execution, Citation Extraction, and Telemetry.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

from app.core.config import RAGSettings
from app.core.logging import get_logger
from app.rag.citations import CitationExtractor
from app.rag.context_builder import ContextBuilder
from app.rag.guardrails import GuardrailPipeline
from app.rag.models import (
    GuardrailResult,
    LLMGenerationOptions,
    LLMUsage,
    RAGMetrics,
    RAGRequest,
    RAGResponse,
    RAGTrace,
    StreamChunk,
)
from app.rag.prompt_builder import PromptBuilder
from app.rag.providers.base import LLMProviderRegistry
from app.retrieval.models import SearchOptions
from app.retrieval.retriever import HybridRetriever

logger = get_logger(__name__)


class RAGOrchestrator:
    """Master orchestrator for end-to-end Retrieval-Augmented Generation."""

    def __init__(
        self,
        retriever: HybridRetriever,
        provider_registry: LLMProviderRegistry,
        context_builder: ContextBuilder | None = None,
        prompt_builder: PromptBuilder | None = None,
        citation_extractor: CitationExtractor | None = None,
        guardrail_pipeline: GuardrailPipeline | None = None,
        settings: RAGSettings | None = None,
    ) -> None:
        """Initialize RAGOrchestrator.

        Args:
            retriever: Injected HybridRetriever instance.
            provider_registry: Pluggable registry containing registered LLM providers.
            context_builder: Context building and token budgeting component.
            prompt_builder: Prompt construction and strategy engine.
            citation_extractor: Citation attribution extractor.
            guardrail_pipeline: Pre and post-generation safety guardrails.
            settings: RAG configuration parameters.
        """
        self._retriever = retriever
        self._registry = provider_registry
        self._settings = settings or RAGSettings()
        self._context_builder = context_builder or ContextBuilder(
            default_token_budget=self._settings.context_token_budget
        )
        self._prompt_builder = prompt_builder or PromptBuilder(settings=self._settings)
        self._citation_extractor = citation_extractor or CitationExtractor()
        self._guardrails = guardrail_pipeline or GuardrailPipeline()

    @property
    def provider_registry(self) -> LLMProviderRegistry:
        """Access registered LLM providers."""
        return self._registry

    async def query(self, request: RAGRequest) -> RAGResponse:
        """Execute end-to-end RAG question answering pipeline.

        Args:
            request: User query and optional runtime configuration overrides.

        Returns:
            RAGResponse: Grounded answer with citations, context chunks, and trace metrics.
        """
        total_start = time.perf_counter()
        latencies: dict[str, float] = {}

        # 1. Resolve Provider, Model, and Strategy
        provider_name = (request.provider or self._settings.llm_provider).lower().strip()
        provider = self._registry.get(provider_name)
        model_name = request.model or provider.default_model
        prompt_strategy_name = request.prompt_strategy or self._settings.prompt_strategy

        # 2. Stage 1: Hybrid Retrieval
        retrieval_start = time.perf_counter()
        retrieval_opts = request.retrieval_options or SearchOptions(
            top_k=20,
            timeout_seconds=self._settings.timeout_seconds,
        )
        retrieval_result = await self._retriever.search(
            query=request.query,
            options=retrieval_opts,
            filters=request.filters,
        )
        latencies["retrieval_ms"] = (time.perf_counter() - retrieval_start) * 1000.0

        # 3. Stage 2: Pre-Generation Guardrails
        guardrail_start = time.perf_counter()
        pre_guard_res: GuardrailResult
        if self._settings.enable_guardrails:
            pre_guard_res = await self._guardrails.run_pre_generation(
                query=request.query,
                chunks=retrieval_result.chunks,
                min_relevance_threshold=self._settings.min_relevance_threshold,
            )
        else:
            pre_guard_res = GuardrailResult(is_safe=True)

        guardrails_duration_ms = (time.perf_counter() - guardrail_start) * 1000.0
        latencies["guardrails_pre_ms"] = guardrails_duration_ms

        # 4. Handle Insufficient Context / Early Fallback
        if not pre_guard_res.is_safe and pre_guard_res.insufficient_context:
            total_duration_ms = (time.perf_counter() - total_start) * 1000.0
            latencies["total_ms"] = total_duration_ms

            metrics = RAGMetrics(
                retrieval_duration_ms=round(latencies["retrieval_ms"], 2),
                guardrails_duration_ms=round(guardrails_duration_ms, 2),
                total_duration_ms=round(total_duration_ms, 2),
                retrieved_chunks_count=len(retrieval_result.chunks),
                used_chunks_count=0,
                dropped_chunks_count=len(retrieval_result.chunks),
                citations_count=0,
            )
            retrieval_strat = (
                ", ".join(retrieval_result.trace.retrieval_strategies)
                if retrieval_result.trace and retrieval_result.trace.retrieval_strategies
                else "hybrid"
            )
            cache_hit = retrieval_result.trace.cache_hit if retrieval_result.trace else False

            trace = RAGTrace(
                query=request.query,
                provider=provider_name,
                model=model_name,
                prompt_strategy=prompt_strategy_name,
                retrieval_strategy=retrieval_strat,
                guardrail_strategies=self._guardrails.get_guardrail_names(),
                latencies={k: round(v, 2) for k, v in latencies.items()},
                token_usage=LLMUsage(),
                retrieved_chunks=len(retrieval_result.chunks),
                used_chunks=0,
                citations_extracted=0,
                cache_hit=cache_hit,
                fallback_used=True,
                fallback_reason=pre_guard_res.fallback_reason,
                guardrail_results=pre_guard_res.checks,
            )
            return RAGResponse(
                query=request.query,
                answer=self._settings.fallback_message,
                citations=[],
                used_chunks=[],
                retrieval_result=retrieval_result,
                guardrail_result=pre_guard_res,
                metrics=metrics,
                trace=trace,
                provider=provider_name,
                model=model_name,
                prompt_strategy=prompt_strategy_name,
            )

        # 5. Stage 3: Context Construction
        context_start = time.perf_counter()
        built_context = self._context_builder.build_context(
            chunks=retrieval_result.chunks,
            token_budget=self._settings.context_token_budget,
        )
        latencies["context_build_ms"] = (time.perf_counter() - context_start) * 1000.0

        # 6. Stage 4: Prompt Construction
        prompt_start = time.perf_counter()
        formatted_prompt = self._prompt_builder.build_prompt(
            query=request.query,
            context=built_context,
            strategy_name=prompt_strategy_name,
            fallback_message=self._settings.fallback_message,
            conversation_history=request.conversation_history,
        )
        latencies["prompt_build_ms"] = (time.perf_counter() - prompt_start) * 1000.0

        # 7. Stage 5: LLM Inference
        gen_opts = request.generation_options or LLMGenerationOptions(
            temperature=self._settings.temperature,
            top_p=self._settings.top_p,
            max_output_tokens=self._settings.max_output_tokens,
            timeout_seconds=self._settings.timeout_seconds,
        )
        llm_start = time.perf_counter()
        llm_response = await provider.generate(
            prompt=formatted_prompt,
            options=gen_opts,
            model=model_name,
        )
        latencies["llm_generation_ms"] = (time.perf_counter() - llm_start) * 1000.0

        # 8. Stage 6: Citation Extraction
        citation_start = time.perf_counter()
        citations = self._citation_extractor.extract_citations(
            text=llm_response.content,
            context=built_context,
        )
        latencies["citations_ms"] = (time.perf_counter() - citation_start) * 1000.0

        # 9. Stage 7: Post-Generation Guardrails
        post_guard_start = time.perf_counter()
        final_guard_res = pre_guard_res
        if self._settings.enable_guardrails:
            final_guard_res = await self._guardrails.run_post_generation(
                query=request.query,
                answer=llm_response.content,
                citations=citations,
                context=built_context,
                initial_result=pre_guard_res,
            )
        post_guard_ms = (time.perf_counter() - post_guard_start) * 1000.0
        latencies["guardrails_post_ms"] = post_guard_ms
        guardrails_duration_ms += post_guard_ms

        total_duration_ms = (time.perf_counter() - total_start) * 1000.0
        latencies["total_ms"] = total_duration_ms

        # 10. Assemble Metrics & Trace
        metrics = RAGMetrics(
            retrieval_duration_ms=round(latencies["retrieval_ms"], 2),
            context_build_duration_ms=round(latencies["context_build_ms"], 2),
            prompt_build_duration_ms=round(latencies["prompt_build_ms"], 2),
            llm_generation_duration_ms=round(latencies["llm_generation_ms"], 2),
            guardrails_duration_ms=round(guardrails_duration_ms, 2),
            citations_duration_ms=round(latencies["citations_ms"], 2),
            total_duration_ms=round(total_duration_ms, 2),
            retrieved_chunks_count=len(retrieval_result.chunks),
            used_chunks_count=len(built_context.chunks),
            dropped_chunks_count=built_context.dropped_chunks_count,
            citations_count=len(citations),
            prompt_tokens=llm_response.usage.prompt_tokens,
            completion_tokens=llm_response.usage.completion_tokens,
            total_tokens=llm_response.usage.total_tokens,
        )

        retrieval_strat = (
            ", ".join(retrieval_result.trace.retrieval_strategies)
            if retrieval_result.trace and retrieval_result.trace.retrieval_strategies
            else "hybrid"
        )
        cache_hit = retrieval_result.trace.cache_hit if retrieval_result.trace else False

        trace = RAGTrace(
            query=request.query,
            provider=provider_name,
            model=model_name,
            prompt_strategy=prompt_strategy_name,
            retrieval_strategy=retrieval_strat,
            guardrail_strategies=self._guardrails.get_guardrail_names(),
            latencies={k: round(v, 2) for k, v in latencies.items()},
            token_usage=llm_response.usage,
            retrieved_chunks=len(retrieval_result.chunks),
            used_chunks=len(built_context.chunks),
            citations_extracted=len(citations),
            cache_hit=cache_hit,
            fallback_used=final_guard_res.fallback_used,
            fallback_reason=final_guard_res.fallback_reason,
            guardrail_results=final_guard_res.checks,
        )

        logger.info(
            "rag_query_completed",
            provider=provider_name,
            model=model_name,
            prompt_strategy=prompt_strategy_name,
            used_chunks=len(built_context.chunks),
            citations=len(citations),
            total_latency_ms=metrics.total_duration_ms,
        )

        return RAGResponse(
            query=request.query,
            answer=llm_response.content,
            citations=citations,
            used_chunks=built_context.chunks,
            retrieval_result=retrieval_result,
            guardrail_result=final_guard_res,
            metrics=metrics,
            trace=trace,
            provider=provider_name,
            model=model_name,
            prompt_strategy=prompt_strategy_name,
        )

    async def stream_query(self, request: RAGRequest) -> AsyncIterator[StreamChunk]:
        """Execute streaming RAG generation for real-time SSE/WebSocket responses."""
        provider_name = (request.provider or self._settings.llm_provider).lower().strip()
        provider = self._registry.get(provider_name)
        model_name = request.model or provider.default_model
        prompt_strategy_name = request.prompt_strategy or self._settings.prompt_strategy

        retrieval_opts = request.retrieval_options or SearchOptions(
            top_k=20,
            timeout_seconds=self._settings.timeout_seconds,
        )
        retrieval_result = await self._retriever.search(
            query=request.query,
            options=retrieval_opts,
            filters=request.filters,
        )

        # Check guardrails
        if self._settings.enable_guardrails:
            guard_res = await self._guardrails.run_pre_generation(
                query=request.query,
                chunks=retrieval_result.chunks,
                min_relevance_threshold=self._settings.min_relevance_threshold,
            )
            if not guard_res.is_safe and guard_res.insufficient_context:
                yield StreamChunk(
                    content=self._settings.fallback_message,
                    finish_reason="stop",
                    is_final=True,
                )
                return

        built_context = self._context_builder.build_context(
            chunks=retrieval_result.chunks,
            token_budget=self._settings.context_token_budget,
        )
        formatted_prompt = self._prompt_builder.build_prompt(
            query=request.query,
            context=built_context,
            strategy_name=prompt_strategy_name,
            fallback_message=self._settings.fallback_message,
            conversation_history=request.conversation_history,
        )
        gen_opts = request.generation_options or LLMGenerationOptions(
            temperature=self._settings.temperature,
            top_p=self._settings.top_p,
            max_output_tokens=self._settings.max_output_tokens,
            timeout_seconds=self._settings.timeout_seconds,
        )

        async for chunk in provider.stream_generate(
            prompt=formatted_prompt,
            options=gen_opts,
            model=model_name,
        ):
            yield chunk
