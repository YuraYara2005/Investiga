"""Asynchronous RAG Evaluator.

Executes end-to-end RAG queries for benchmark evaluation samples, computes
retrieval and generation quality metrics, collects stage latencies, and
generates evaluation reports with structured logging and concurrency control.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.evaluation.metrics import (
    GenerationMetricsCalculator,
    RetrievalMetricsCalculator,
    compute_overall_stats,
)
from app.evaluation.models import (
    EvaluationConfiguration,
    EvaluationRawTrace,
    EvaluationReport,
    EvaluationResult,
    EvaluationRunMetadata,
    EvaluationSample,
    OverallMetrics,
)
from app.rag.models import RAGRequest, RAGResponse
from app.rag.service import RAGService

logger = get_logger(__name__)

# Type alias for progress callbacks
ProgressCallback = Callable[[int, int, str], None]


class RAGEvaluator:
    """Asynchronous evaluator executing RAG queries against benchmark datasets.

    Uses the existing RAGService (dependency injection) to run full end-to-end
    RAG pipeline for each evaluation sample, computes retrieval and generation
    quality metrics, and assembles evaluation reports.

    Args:
        rag_service: Injected RAGService instance.
    """

    def __init__(self, rag_service: RAGService) -> None:
        self._rag_service = rag_service

    async def evaluate_sample(
        self,
        sample: EvaluationSample,
        config: EvaluationConfiguration,
    ) -> EvaluationResult:
        """Evaluate a single benchmark sample through the full RAG pipeline.

        Args:
            sample: Benchmark evaluation sample.
            config: Evaluation configuration.

        Returns:
            EvaluationResult with metrics, trace, and metadata.
        """
        start_time = time.perf_counter()

        try:
            # Execute RAG query
            request = RAGRequest(
                query=sample.question,
                provider=config.provider_override,
                model=config.model_override,
                prompt_strategy=config.prompt_strategy,
            )

            response: RAGResponse = await self._rag_service.query(request)
            total_time_ms = (time.perf_counter() - start_time) * 1000.0

            # Extract retrieved document IDs for metric computation
            retrieved_doc_ids = [
                str(chunk.document_id) for chunk in response.used_chunks
            ]
            retrieved_chunk_ids = [
                str(chunk.chunk_id) for chunk in response.used_chunks
            ]
            retrieved_scores = [chunk.score for chunk in response.used_chunks]

            # Context texts for faithfulness evaluation
            context_texts = [chunk.text for chunk in response.used_chunks]

            # Valid citation source indices
            valid_source_indices = {
                chunk.source_index for chunk in response.used_chunks
            }

            # Compute retrieval metrics
            retrieval_metrics = RetrievalMetricsCalculator.compute_all(
                retrieved_ids=retrieved_doc_ids,
                relevant_ids=sample.expected_documents,
                scores=retrieved_scores,
                retrieval_latency_ms=response.metrics.retrieval_duration_ms,
                k_values=config.k_values,
            )

            # Compute generation metrics
            generation_metrics = GenerationMetricsCalculator.compute_all(
                answer=response.answer,
                question=sample.question,
                context_texts=context_texts,
                valid_source_indices=valid_source_indices,
                total_context_chunks=len(response.used_chunks),
                expected_keywords=sample.expected_keywords or None,
                prompt_tokens=response.metrics.prompt_tokens,
                completion_tokens=response.metrics.completion_tokens,
                total_tokens=response.metrics.total_tokens,
                llm_latency_ms=response.metrics.llm_generation_duration_ms,
                overall_response_time_ms=total_time_ms,
            )

            # Build raw trace
            raw_trace = EvaluationRawTrace(
                question=sample.question,
                retrieved_chunk_ids=retrieved_chunk_ids,
                retrieved_chunk_texts=context_texts[:10],  # Cap for storage
                retrieved_scores=retrieved_scores,
                context_text=response.trace.query if response.trace else "",
                prompt_system="",  # Not exposed by RAGResponse
                prompt_user="",
                provider=response.provider,
                model=response.model,
                generated_answer=response.answer,
                extracted_citations=[
                    {"index": c.source_index, "chunk_id": c.chunk_id, "title": c.title}
                    for c in response.citations
                ],
                retrieval_latency_ms=response.metrics.retrieval_duration_ms,
                context_build_latency_ms=response.metrics.context_build_duration_ms,
                prompt_build_latency_ms=response.metrics.prompt_build_duration_ms,
                llm_latency_ms=response.metrics.llm_generation_duration_ms,
                citation_latency_ms=response.metrics.citations_duration_ms,
                total_latency_ms=total_time_ms,
            )

            result = EvaluationResult(
                sample_id=sample.id,
                question=sample.question,
                expected_answer=sample.expected_answer,
                generated_answer=response.answer,
                provider=response.provider,
                model=response.model,
                prompt_strategy=response.prompt_strategy,
                retrieval_metrics=retrieval_metrics,
                generation_metrics=generation_metrics,
                citations_count=len(response.citations),
                retrieved_chunks_count=len(response.retrieval_result.chunks),
                used_chunks_count=len(response.used_chunks),
                success=True,
                raw_trace=raw_trace,
            )

            logger.debug(
                "sample_evaluated",
                sample_id=sample.id,
                faithfulness=generation_metrics.faithfulness,
                recall_at_5=retrieval_metrics.recall_at_5,
                latency_ms=round(total_time_ms, 2),
            )
            return result

        except Exception as exc:
            total_time_ms = (time.perf_counter() - start_time) * 1000.0
            logger.warning(
                "sample_evaluation_failed",
                sample_id=sample.id,
                error=str(exc),
                latency_ms=round(total_time_ms, 2),
            )
            return EvaluationResult(
                sample_id=sample.id,
                question=sample.question,
                expected_answer=sample.expected_answer,
                generated_answer="",
                success=False,
                error_message=str(exc),
                raw_trace=EvaluationRawTrace(
                    question=sample.question,
                    total_latency_ms=total_time_ms,
                ),
            )

    async def evaluate_dataset(
        self,
        samples: list[EvaluationSample],
        config: EvaluationConfiguration,
        progress_callback: ProgressCallback | None = None,
    ) -> EvaluationReport:
        """Evaluate all samples in a dataset with concurrency and timeout control.

        Uses asyncio.Semaphore to limit concurrency and asyncio.wait_for for
        per-sample timeout. Provides structured logging and optional progress
        callbacks.

        Args:
            samples: List of evaluation samples.
            config: Evaluation configuration.
            progress_callback: Optional callback(completed, total, sample_id).

        Returns:
            EvaluationReport with all results and aggregate metrics.
        """
        started_at = datetime.now(UTC)
        total_start = time.perf_counter()

        logger.info(
            "dataset_evaluation_started",
            total_samples=len(samples),
            concurrency=config.max_concurrency,
            timeout_seconds=config.timeout_seconds,
            provider=config.provider_override or "default",
        )

        semaphore = asyncio.Semaphore(config.max_concurrency)
        completed_count = 0
        results: list[EvaluationResult] = []

        async def _evaluate_with_limits(
            sample: EvaluationSample,
        ) -> EvaluationResult:
            nonlocal completed_count
            async with semaphore:
                try:
                    result = await asyncio.wait_for(
                        self.evaluate_sample(sample, config),
                        timeout=config.timeout_seconds,
                    )
                except TimeoutError:
                    result = EvaluationResult(
                        sample_id=sample.id,
                        question=sample.question,
                        expected_answer=sample.expected_answer,
                        success=False,
                        error_message=f"Timeout after {config.timeout_seconds}s",
                        raw_trace=EvaluationRawTrace(
                            question=sample.question,
                            total_latency_ms=config.timeout_seconds * 1000,
                        ),
                    )

                completed_count += 1
                if progress_callback:
                    progress_callback(completed_count, len(samples), sample.id)

                if completed_count % max(1, len(samples) // 10) == 0:
                    logger.info(
                        "evaluation_progress",
                        completed=completed_count,
                        total=len(samples),
                        percent=round(completed_count / len(samples) * 100, 1),
                    )
                return result

        tasks = [_evaluate_with_limits(s) for s in samples]
        results = await asyncio.gather(*tasks)

        total_duration = time.perf_counter() - total_start
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        # Compute overall metrics
        overall_retrieval = _compute_overall_retrieval_metrics(successful)
        overall_generation = _compute_overall_generation_metrics(successful)

        run_metadata = EvaluationRunMetadata(
            started_at=started_at,
            completed_at=datetime.now(UTC),
            provider=config.provider_override or "default",
            dataset_name=config.dataset_name,
            total_samples=len(samples),
            successful_samples=len(successful),
            failed_samples=len(failed),
            total_duration_seconds=round(total_duration, 2),
            configuration=config,
        )

        # Build summary
        summary = _build_summary(successful, failed)

        report = EvaluationReport(
            run_metadata=run_metadata,
            results=list(results),
            overall_retrieval_metrics=overall_retrieval,
            overall_generation_metrics=overall_generation,
            configuration=config,
            summary=summary,
        )

        logger.info(
            "dataset_evaluation_completed",
            total_samples=len(samples),
            successful=len(successful),
            failed=len(failed),
            duration_seconds=round(total_duration, 2),
        )

        return report


def _compute_overall_retrieval_metrics(
    results: list[EvaluationResult],
) -> list[OverallMetrics]:
    """Compute aggregate retrieval metrics across successful results."""
    if not results:
        return []

    metrics_map: dict[str, list[float]] = {
        "recall_at_1": [],
        "recall_at_3": [],
        "recall_at_5": [],
        "recall_at_10": [],
        "recall_at_20": [],
        "precision_at_k": [],
        "mrr": [],
        "map_score": [],
        "ndcg": [],
        "hit_rate": [],
        "context_precision": [],
        "context_recall": [],
        "avg_similarity_score": [],
        "avg_retrieval_latency_ms": [],
    }

    for r in results:
        m = r.retrieval_metrics
        metrics_map["recall_at_1"].append(m.recall_at_1)
        metrics_map["recall_at_3"].append(m.recall_at_3)
        metrics_map["recall_at_5"].append(m.recall_at_5)
        metrics_map["recall_at_10"].append(m.recall_at_10)
        metrics_map["recall_at_20"].append(m.recall_at_20)
        metrics_map["precision_at_k"].append(m.precision_at_k)
        metrics_map["mrr"].append(m.mrr)
        metrics_map["map_score"].append(m.map_score)
        metrics_map["ndcg"].append(m.ndcg)
        metrics_map["hit_rate"].append(m.hit_rate)
        metrics_map["context_precision"].append(m.context_precision)
        metrics_map["context_recall"].append(m.context_recall)
        metrics_map["avg_similarity_score"].append(m.avg_similarity_score)
        metrics_map["avg_retrieval_latency_ms"].append(m.avg_retrieval_latency_ms)

    overall: list[OverallMetrics] = []
    for name, values in metrics_map.items():
        stats = compute_overall_stats(values, name)
        overall.append(OverallMetrics(**stats))
    return overall


def _compute_overall_generation_metrics(
    results: list[EvaluationResult],
) -> list[OverallMetrics]:
    """Compute aggregate generation metrics across successful results."""
    if not results:
        return []

    metrics_map: dict[str, list[float]] = {
        "faithfulness": [],
        "answer_relevancy": [],
        "citation_coverage": [],
        "citation_precision": [],
        "hallucination_rate": [],
        "context_utilization": [],
        "answer_length": [],
        "word_count": [],
        "prompt_tokens": [],
        "completion_tokens": [],
        "total_tokens": [],
        "llm_latency_ms": [],
        "overall_response_time_ms": [],
    }

    for r in results:
        m = r.generation_metrics
        metrics_map["faithfulness"].append(m.faithfulness)
        metrics_map["answer_relevancy"].append(m.answer_relevancy)
        metrics_map["citation_coverage"].append(m.citation_coverage)
        metrics_map["citation_precision"].append(m.citation_precision)
        metrics_map["hallucination_rate"].append(m.hallucination_rate)
        metrics_map["context_utilization"].append(m.context_utilization)
        metrics_map["answer_length"].append(float(m.answer_length))
        metrics_map["word_count"].append(float(m.word_count))
        metrics_map["prompt_tokens"].append(float(m.prompt_tokens))
        metrics_map["completion_tokens"].append(float(m.completion_tokens))
        metrics_map["total_tokens"].append(float(m.total_tokens))
        metrics_map["llm_latency_ms"].append(m.llm_latency_ms)
        metrics_map["overall_response_time_ms"].append(m.overall_response_time_ms)

    overall: list[OverallMetrics] = []
    for name, values in metrics_map.items():
        stats = compute_overall_stats(values, name)
        overall.append(OverallMetrics(**stats))
    return overall


def _build_summary(
    successful: list[EvaluationResult],
    failed: list[EvaluationResult],
) -> dict[str, Any]:
    """Build a summary statistics dictionary."""
    if not successful:
        return {
            "total_evaluated": len(successful) + len(failed),
            "successful": 0,
            "failed": len(failed),
        }

    avg_faith = sum(r.generation_metrics.faithfulness for r in successful) / len(successful)
    avg_halluc = sum(r.generation_metrics.hallucination_rate for r in successful) / len(successful)
    avg_recall5 = sum(r.retrieval_metrics.recall_at_5 for r in successful) / len(successful)
    avg_mrr = sum(r.retrieval_metrics.mrr for r in successful) / len(successful)
    avg_cit_cov = sum(r.generation_metrics.citation_coverage for r in successful) / len(successful)
    avg_latency = sum(r.generation_metrics.overall_response_time_ms for r in successful) / len(successful)
    avg_tokens = sum(r.generation_metrics.total_tokens for r in successful) / len(successful)
    avg_answer_len = sum(r.generation_metrics.answer_length for r in successful) / len(successful)
    avg_chunks = sum(r.used_chunks_count for r in successful) / len(successful)
    avg_prompt_tokens = sum(r.generation_metrics.prompt_tokens for r in successful) / len(successful)
    avg_completion_tokens = sum(r.generation_metrics.completion_tokens for r in successful) / len(successful)

    return {
        "total_evaluated": len(successful) + len(failed),
        "successful": len(successful),
        "failed": len(failed),
        "avg_faithfulness": round(avg_faith, 4),
        "avg_hallucination_rate": round(avg_halluc, 4),
        "avg_recall_at_5": round(avg_recall5, 4),
        "avg_mrr": round(avg_mrr, 4),
        "avg_citation_coverage": round(avg_cit_cov, 4),
        "avg_latency_ms": round(avg_latency, 2),
        "avg_total_tokens": round(avg_tokens, 1),
        "avg_answer_length": round(avg_answer_len, 1),
        "avg_retrieved_chunks": round(avg_chunks, 1),
        "avg_prompt_tokens": round(avg_prompt_tokens, 1),
        "avg_completion_tokens": round(avg_completion_tokens, 1),
        "top_failed_questions": [
            {"question": r.question, "error": r.error_message}
            for r in failed[:20]
        ],
    }
