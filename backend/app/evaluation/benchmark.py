"""Multi-Provider RAG Benchmark Engine.

Evaluates multiple LLM providers against identical benchmark datasets, computes
per-provider aggregate metrics, generates weighted composite leaderboard rankings,
and produces BenchmarkResult containers for comparison and reporting.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.evaluation.evaluator import RAGEvaluator
from app.evaluation.models import (
    BenchmarkResult,
    EvaluationConfiguration,
    EvaluationReport,
    EvaluationSample,
    ProviderBenchmark,
)

logger = get_logger(__name__)

# Default composite score weights for leaderboard ranking
DEFAULT_WEIGHTS: dict[str, float] = {
    "faithfulness": 0.25,
    "hallucination_rate": 0.20,  # Lower is better — will be inverted
    "citation_coverage": 0.15,
    "recall_at_5": 0.15,
    "latency": 0.15,  # Lower is better — will be inverted
    "answer_relevancy": 0.10,
}


class RAGBenchmark:
    """Multi-provider benchmark engine for RAG evaluation comparison.

    Evaluates the same dataset against multiple providers, computes per-provider
    aggregate metrics, and generates a weighted composite leaderboard.

    Args:
        evaluator: Injected RAGEvaluator instance.
        providers: List of provider name strings to benchmark.
        weights: Optional custom leaderboard scoring weights.
    """

    def __init__(
        self,
        evaluator: RAGEvaluator,
        providers: list[str] | None = None,
        weights: dict[str, float] | None = None,
    ) -> None:
        self._evaluator = evaluator
        self._providers = providers or ["mock"]
        self._weights = weights or DEFAULT_WEIGHTS

    @property
    def providers(self) -> list[str]:
        """List of providers to benchmark."""
        return list(self._providers)

    async def run(
        self,
        samples: list[EvaluationSample],
        config: EvaluationConfiguration,
    ) -> BenchmarkResult:
        """Execute benchmark across all configured providers.

        Args:
            samples: Evaluation samples to benchmark against.
            config: Base evaluation configuration (provider will be overridden).

        Returns:
            BenchmarkResult with per-provider results and leaderboard.
        """
        logger.info(
            "benchmark_started",
            providers=self._providers,
            sample_count=len(samples),
        )

        provider_benchmarks: list[ProviderBenchmark] = []
        provider_reports: dict[str, EvaluationReport] = {}

        for provider_name in self._providers:
            logger.info(
                "benchmark_provider_started",
                provider=provider_name,
                sample_count=len(samples),
            )

            # Override provider for this run
            provider_config = EvaluationConfiguration(
                k_values=config.k_values,
                max_concurrency=config.max_concurrency,
                timeout_seconds=config.timeout_seconds,
                providers=[provider_name],
                prompt_strategy=config.prompt_strategy,
                provider_override=provider_name,
                model_override=config.model_override,
                dataset_name=config.dataset_name,
                description=f"Benchmark run for provider: {provider_name}",
                metadata={**config.metadata, "benchmark_provider": provider_name},
            )

            report = await self._evaluator.evaluate_dataset(
                samples=samples,
                config=provider_config,
            )
            provider_reports[provider_name] = report

            # Aggregate provider metrics
            benchmark = _aggregate_provider_metrics(provider_name, report)
            provider_benchmarks.append(benchmark)

            logger.info(
                "benchmark_provider_completed",
                provider=provider_name,
                successful=report.run_metadata.successful_samples,
                failed=report.run_metadata.failed_samples,
                composite_score=benchmark.composite_score,
            )

        # Compute leaderboard
        leaderboard = self._compute_leaderboard(provider_benchmarks)

        result = BenchmarkResult(
            created_at=datetime.now(UTC),
            dataset_name=config.dataset_name,
            total_samples=len(samples),
            providers=provider_benchmarks,
            leaderboard=leaderboard,
            configuration=config,
            metadata={
                "provider_count": len(self._providers),
                "weights": self._weights,
            },
        )

        logger.info(
            "benchmark_completed",
            providers=self._providers,
            total_samples=len(samples),
            winner=leaderboard[0]["provider"] if leaderboard else "N/A",
        )

        return result

    def _compute_leaderboard(
        self,
        benchmarks: list[ProviderBenchmark],
    ) -> list[dict[str, Any]]:
        """Compute weighted composite leaderboard ranking.

        Args:
            benchmarks: List of per-provider benchmark results.

        Returns:
            Sorted leaderboard with rank, provider, composite score, and metrics.
        """
        scored: list[dict[str, Any]] = []

        for b in benchmarks:
            composite = self._compute_composite_score(b)
            scored.append({
                "provider": b.provider_name,
                "model": b.model_name,
                "composite_score": round(composite, 4),
                "avg_faithfulness": round(b.avg_faithfulness, 4),
                "avg_hallucination_rate": round(b.avg_hallucination_rate, 4),
                "avg_citation_coverage": round(b.avg_citation_coverage, 4),
                "avg_recall_at_5": round(b.avg_recall_at_5, 4),
                "avg_latency_ms": round(b.avg_latency_ms, 2),
                "avg_answer_relevancy": round(b.avg_answer_relevancy, 4),
                "avg_token_usage": round(b.avg_token_usage, 1),
                "total_samples": b.total_samples,
                "successful_samples": b.successful_samples,
            })

        # Sort by composite score descending
        scored.sort(key=lambda x: x["composite_score"], reverse=True)

        # Add rank
        for rank, entry in enumerate(scored, start=1):
            entry["rank"] = rank

        return scored

    def _compute_composite_score(self, benchmark: ProviderBenchmark) -> float:
        """Compute weighted composite quality score for a provider.

        Higher is better. Metrics where lower is better (hallucination, latency)
        are inverted.

        Args:
            benchmark: Provider benchmark metrics.

        Returns:
            Composite score as float.
        """
        w = self._weights
        score = 0.0

        # Direct metrics (higher is better)
        score += w.get("faithfulness", 0.0) * benchmark.avg_faithfulness
        score += w.get("citation_coverage", 0.0) * benchmark.avg_citation_coverage
        score += w.get("recall_at_5", 0.0) * benchmark.avg_recall_at_5
        score += w.get("answer_relevancy", 0.0) * benchmark.avg_answer_relevancy

        # Inverted metrics (lower is better)
        halluc_weight = w.get("hallucination_rate", 0.0)
        score += halluc_weight * (1.0 - benchmark.avg_hallucination_rate)

        latency_weight = w.get("latency", 0.0)
        # Normalize latency: assume 5000ms is the worst case
        normalized_latency = min(1.0, benchmark.avg_latency_ms / 5000.0)
        score += latency_weight * (1.0 - normalized_latency)

        return score


def _aggregate_provider_metrics(
    provider_name: str,
    report: EvaluationReport,
) -> ProviderBenchmark:
    """Aggregate metrics from an evaluation report into a ProviderBenchmark.

    Args:
        provider_name: Name of the provider.
        report: Evaluation report for this provider.

    Returns:
        ProviderBenchmark with averaged metrics.
    """
    successful = [r for r in report.results if r.success]

    if not successful:
        return ProviderBenchmark(
            provider_name=provider_name,
            total_samples=report.run_metadata.total_samples,
            successful_samples=0,
        )

    n = len(successful)

    # Extract model name from first successful result
    model_name = successful[0].model if successful else ""

    avg_latency = sum(r.generation_metrics.overall_response_time_ms for r in successful) / n
    avg_retrieval = sum(r.retrieval_metrics.avg_similarity_score for r in successful) / n
    avg_faith = sum(r.generation_metrics.faithfulness for r in successful) / n
    avg_halluc = sum(r.generation_metrics.hallucination_rate for r in successful) / n
    avg_cit_cov = sum(r.generation_metrics.citation_coverage for r in successful) / n
    avg_cit_prec = sum(r.generation_metrics.citation_precision for r in successful) / n
    avg_relevancy = sum(r.generation_metrics.answer_relevancy for r in successful) / n
    avg_answer_len = sum(r.generation_metrics.answer_length for r in successful) / n
    avg_tokens = sum(r.generation_metrics.total_tokens for r in successful) / n
    avg_prompt_tok = sum(r.generation_metrics.prompt_tokens for r in successful) / n
    avg_comp_tok = sum(r.generation_metrics.completion_tokens for r in successful) / n
    avg_ctx_util = sum(r.generation_metrics.context_utilization for r in successful) / n
    avg_recall5 = sum(r.retrieval_metrics.recall_at_5 for r in successful) / n
    avg_mrr = sum(r.retrieval_metrics.mrr for r in successful) / n

    return ProviderBenchmark(
        provider_name=provider_name,
        model_name=model_name,
        total_samples=report.run_metadata.total_samples,
        successful_samples=n,
        avg_latency_ms=round(avg_latency, 2),
        avg_retrieval_score=round(avg_retrieval, 4),
        avg_faithfulness=round(avg_faith, 4),
        avg_hallucination_rate=round(avg_halluc, 4),
        avg_citation_coverage=round(avg_cit_cov, 4),
        avg_citation_precision=round(avg_cit_prec, 4),
        avg_answer_relevancy=round(avg_relevancy, 4),
        avg_answer_length=round(avg_answer_len, 1),
        avg_token_usage=round(avg_tokens, 1),
        avg_prompt_tokens=round(avg_prompt_tok, 1),
        avg_completion_tokens=round(avg_comp_tok, 1),
        avg_context_utilization=round(avg_ctx_util, 4),
        avg_recall_at_5=round(avg_recall5, 4),
        avg_mrr=round(avg_mrr, 4),
        composite_score=0.0,  # Computed later in leaderboard
        report=report,
    )
