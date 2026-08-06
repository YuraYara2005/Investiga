"""Notebook Analytics Layer for RAG Evaluation.

Provides DataFrame builders that convert evaluation results, provider benchmarks,
and leaderboards into structured tabular data. Returns pandas.DataFrame when
pandas is available; otherwise gracefully falls back to dict[str, list] without
failing.

Designed for Jupyter notebook consumption:
    display(df)
    df.head()
    df.describe()
    df.to_excel()
    df.to_csv()
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.evaluation.models import (
    BenchmarkResult,
    EvaluationResult,
)

logger = get_logger(__name__)

# Soft import of pandas
_PANDAS_AVAILABLE = False
try:
    import pandas as _pd  # type: ignore[import-untyped]

    _PANDAS_AVAILABLE = True
except ImportError:
    _pd = None


def _to_dataframe_or_dict(
    data: dict[str, list[Any]],
) -> Any:
    """Convert dict[str, list] to pd.DataFrame if pandas is available.

    Args:
        data: Column-oriented dictionary.

    Returns:
        pd.DataFrame if pandas installed, else dict[str, list].
    """
    if _PANDAS_AVAILABLE and _pd is not None:
        return _pd.DataFrame(data)
    return data


class EvaluationDataFrameBuilder:
    """Converts evaluation results into per-sample DataFrames."""

    @staticmethod
    def results_to_dataframe(
        results: list[EvaluationResult],
    ) -> Any:
        """Convert evaluation results to a tabular DataFrame.

        Each row represents one evaluated sample with all key metrics.

        Args:
            results: List of EvaluationResult objects.

        Returns:
            pd.DataFrame or dict[str, list].
        """
        data: dict[str, list[Any]] = {
            "sample_id": [],
            "question": [],
            "success": [],
            "provider": [],
            "model": [],
            "faithfulness": [],
            "hallucination_rate": [],
            "answer_relevancy": [],
            "citation_coverage": [],
            "citation_precision": [],
            "context_utilization": [],
            "recall_at_1": [],
            "recall_at_3": [],
            "recall_at_5": [],
            "recall_at_10": [],
            "mrr": [],
            "map_score": [],
            "ndcg": [],
            "hit_rate": [],
            "answer_length": [],
            "word_count": [],
            "prompt_tokens": [],
            "completion_tokens": [],
            "total_tokens": [],
            "llm_latency_ms": [],
            "overall_response_time_ms": [],
            "retrieved_chunks": [],
            "used_chunks": [],
            "citations_count": [],
            "error_message": [],
        }

        for r in results:
            data["sample_id"].append(r.sample_id)
            data["question"].append(r.question[:200])
            data["success"].append(r.success)
            data["provider"].append(r.provider)
            data["model"].append(r.model)
            data["faithfulness"].append(r.generation_metrics.faithfulness)
            data["hallucination_rate"].append(r.generation_metrics.hallucination_rate)
            data["answer_relevancy"].append(r.generation_metrics.answer_relevancy)
            data["citation_coverage"].append(r.generation_metrics.citation_coverage)
            data["citation_precision"].append(r.generation_metrics.citation_precision)
            data["context_utilization"].append(r.generation_metrics.context_utilization)
            data["recall_at_1"].append(r.retrieval_metrics.recall_at_1)
            data["recall_at_3"].append(r.retrieval_metrics.recall_at_3)
            data["recall_at_5"].append(r.retrieval_metrics.recall_at_5)
            data["recall_at_10"].append(r.retrieval_metrics.recall_at_10)
            data["mrr"].append(r.retrieval_metrics.mrr)
            data["map_score"].append(r.retrieval_metrics.map_score)
            data["ndcg"].append(r.retrieval_metrics.ndcg)
            data["hit_rate"].append(r.retrieval_metrics.hit_rate)
            data["answer_length"].append(r.generation_metrics.answer_length)
            data["word_count"].append(r.generation_metrics.word_count)
            data["prompt_tokens"].append(r.generation_metrics.prompt_tokens)
            data["completion_tokens"].append(r.generation_metrics.completion_tokens)
            data["total_tokens"].append(r.generation_metrics.total_tokens)
            data["llm_latency_ms"].append(r.generation_metrics.llm_latency_ms)
            data["overall_response_time_ms"].append(r.generation_metrics.overall_response_time_ms)
            data["retrieved_chunks"].append(r.retrieved_chunks_count)
            data["used_chunks"].append(r.used_chunks_count)
            data["citations_count"].append(r.citations_count)
            data["error_message"].append(r.error_message or "")

        return _to_dataframe_or_dict(data)


class ProviderComparisonFrame:
    """Converts benchmark provider data into a comparison DataFrame."""

    @staticmethod
    def benchmark_to_dataframe(benchmark: BenchmarkResult) -> Any:
        """Convert benchmark provider results to a comparison table.

        Args:
            benchmark: Benchmark result.

        Returns:
            pd.DataFrame or dict[str, list].
        """
        data: dict[str, list[Any]] = {
            "provider": [],
            "model": [],
            "total_samples": [],
            "successful_samples": [],
            "avg_latency_ms": [],
            "avg_faithfulness": [],
            "avg_hallucination_rate": [],
            "avg_citation_coverage": [],
            "avg_citation_precision": [],
            "avg_answer_relevancy": [],
            "avg_recall_at_5": [],
            "avg_mrr": [],
            "avg_token_usage": [],
            "avg_prompt_tokens": [],
            "avg_completion_tokens": [],
            "avg_answer_length": [],
            "avg_context_utilization": [],
            "composite_score": [],
        }

        for p in benchmark.providers:
            data["provider"].append(p.provider_name)
            data["model"].append(p.model_name)
            data["total_samples"].append(p.total_samples)
            data["successful_samples"].append(p.successful_samples)
            data["avg_latency_ms"].append(p.avg_latency_ms)
            data["avg_faithfulness"].append(p.avg_faithfulness)
            data["avg_hallucination_rate"].append(p.avg_hallucination_rate)
            data["avg_citation_coverage"].append(p.avg_citation_coverage)
            data["avg_citation_precision"].append(p.avg_citation_precision)
            data["avg_answer_relevancy"].append(p.avg_answer_relevancy)
            data["avg_recall_at_5"].append(p.avg_recall_at_5)
            data["avg_mrr"].append(p.avg_mrr)
            data["avg_token_usage"].append(p.avg_token_usage)
            data["avg_prompt_tokens"].append(p.avg_prompt_tokens)
            data["avg_completion_tokens"].append(p.avg_completion_tokens)
            data["avg_answer_length"].append(p.avg_answer_length)
            data["avg_context_utilization"].append(p.avg_context_utilization)
            data["composite_score"].append(p.composite_score)

        return _to_dataframe_or_dict(data)


class LeaderboardFrame:
    """Converts benchmark leaderboard into a ranked DataFrame."""

    @staticmethod
    def to_dataframe(benchmark: BenchmarkResult) -> Any:
        """Convert leaderboard to a ranked table.

        Args:
            benchmark: Benchmark result with leaderboard.

        Returns:
            pd.DataFrame or dict[str, list].
        """
        if not benchmark.leaderboard:
            return _to_dataframe_or_dict({"rank": [], "provider": [], "composite_score": []})

        data: dict[str, list[Any]] = {k: [] for k in benchmark.leaderboard[0].keys()}
        for entry in benchmark.leaderboard:
            for k, v in entry.items():
                data[k].append(v)

        return _to_dataframe_or_dict(data)


class RetrievalMetricsFrame:
    """Converts evaluation results into retrieval-focused DataFrames."""

    @staticmethod
    def to_dataframe(results: list[EvaluationResult]) -> Any:
        """Build retrieval metrics DataFrame.

        Args:
            results: List of evaluation results.

        Returns:
            pd.DataFrame or dict[str, list].
        """
        data: dict[str, list[Any]] = {
            "sample_id": [],
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
            data["sample_id"].append(r.sample_id)
            data["recall_at_1"].append(m.recall_at_1)
            data["recall_at_3"].append(m.recall_at_3)
            data["recall_at_5"].append(m.recall_at_5)
            data["recall_at_10"].append(m.recall_at_10)
            data["recall_at_20"].append(m.recall_at_20)
            data["precision_at_k"].append(m.precision_at_k)
            data["mrr"].append(m.mrr)
            data["map_score"].append(m.map_score)
            data["ndcg"].append(m.ndcg)
            data["hit_rate"].append(m.hit_rate)
            data["context_precision"].append(m.context_precision)
            data["context_recall"].append(m.context_recall)
            data["avg_similarity_score"].append(m.avg_similarity_score)
            data["avg_retrieval_latency_ms"].append(m.avg_retrieval_latency_ms)

        return _to_dataframe_or_dict(data)


class GenerationMetricsFrame:
    """Converts evaluation results into generation-focused DataFrames."""

    @staticmethod
    def to_dataframe(results: list[EvaluationResult]) -> Any:
        """Build generation metrics DataFrame.

        Args:
            results: List of evaluation results.

        Returns:
            pd.DataFrame or dict[str, list].
        """
        data: dict[str, list[Any]] = {
            "sample_id": [],
            "faithfulness": [],
            "hallucination_rate": [],
            "answer_relevancy": [],
            "citation_coverage": [],
            "citation_precision": [],
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
            data["sample_id"].append(r.sample_id)
            data["faithfulness"].append(m.faithfulness)
            data["hallucination_rate"].append(m.hallucination_rate)
            data["answer_relevancy"].append(m.answer_relevancy)
            data["citation_coverage"].append(m.citation_coverage)
            data["citation_precision"].append(m.citation_precision)
            data["context_utilization"].append(m.context_utilization)
            data["answer_length"].append(m.answer_length)
            data["word_count"].append(m.word_count)
            data["prompt_tokens"].append(m.prompt_tokens)
            data["completion_tokens"].append(m.completion_tokens)
            data["total_tokens"].append(m.total_tokens)
            data["llm_latency_ms"].append(m.llm_latency_ms)
            data["overall_response_time_ms"].append(m.overall_response_time_ms)

        return _to_dataframe_or_dict(data)


class QuestionAnalysisFrame:
    """Per-question analysis with answer text and trace data."""

    @staticmethod
    def to_dataframe(results: list[EvaluationResult]) -> Any:
        """Build question-level analysis DataFrame.

        Args:
            results: List of evaluation results.

        Returns:
            pd.DataFrame or dict[str, list].
        """
        data: dict[str, list[Any]] = {
            "sample_id": [],
            "question": [],
            "generated_answer": [],
            "expected_answer": [],
            "provider": [],
            "faithfulness": [],
            "recall_at_5": [],
            "citation_coverage": [],
            "total_latency_ms": [],
            "citations_count": [],
            "success": [],
        }

        for r in results:
            data["sample_id"].append(r.sample_id)
            data["question"].append(r.question[:200])
            data["generated_answer"].append(r.generated_answer[:300])
            data["expected_answer"].append(r.expected_answer[:300])
            data["provider"].append(r.provider)
            data["faithfulness"].append(r.generation_metrics.faithfulness)
            data["recall_at_5"].append(r.retrieval_metrics.recall_at_5)
            data["citation_coverage"].append(r.generation_metrics.citation_coverage)
            data["total_latency_ms"].append(r.generation_metrics.overall_response_time_ms)
            data["citations_count"].append(r.citations_count)
            data["success"].append(r.success)

        return _to_dataframe_or_dict(data)


class FailureAnalysisFrame:
    """Focused analysis of failed evaluation samples."""

    @staticmethod
    def to_dataframe(results: list[EvaluationResult]) -> Any:
        """Build failure analysis DataFrame from failed results.

        Args:
            results: List of evaluation results (filters to failures).

        Returns:
            pd.DataFrame or dict[str, list].
        """
        failed = [r for r in results if not r.success]

        data: dict[str, list[Any]] = {
            "sample_id": [],
            "question": [],
            "error_message": [],
            "provider": [],
            "total_latency_ms": [],
        }

        for r in failed:
            data["sample_id"].append(r.sample_id)
            data["question"].append(r.question[:200])
            data["error_message"].append(r.error_message or "Unknown")
            data["provider"].append(r.provider)
            data["total_latency_ms"].append(r.raw_trace.total_latency_ms if r.raw_trace else 0.0)

        return _to_dataframe_or_dict(data)
