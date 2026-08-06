"""Report Generation for RAG Evaluation Results.

Generates Markdown reports, summary statistics tables, provider leaderboards,
category/difficulty breakdowns, top failure cases, and detailed metric comparisons
for evaluation reports and benchmark results.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.evaluation.metrics import compute_overall_stats
from app.evaluation.models import (
    BenchmarkResult,
    EvaluationReport,
    EvaluationResult,
    OverallMetrics,
)

logger = get_logger(__name__)


class ReportGenerator:
    """Generates formatted reports from evaluation and benchmark results."""

    @staticmethod
    def generate_markdown(report: EvaluationReport) -> str:
        """Generate a comprehensive Markdown evaluation report.

        Args:
            report: Evaluation report to render.

        Returns:
            Markdown formatted string.
        """
        lines: list[str] = []
        meta = report.run_metadata
        summary = report.summary

        lines.append("# RAG Evaluation Report")
        lines.append("")
        lines.append(f"**Run ID:** `{meta.run_id}`")
        lines.append(f"**Provider:** {meta.provider}")
        lines.append(f"**Dataset:** {meta.dataset_name}")
        lines.append(f"**Started:** {meta.started_at.isoformat() if meta.started_at else 'N/A'}")
        lines.append(f"**Duration:** {meta.total_duration_seconds:.1f}s")
        lines.append(f"**Total Samples:** {meta.total_samples}")
        lines.append(f"**Successful:** {meta.successful_samples}")
        lines.append(f"**Failed:** {meta.failed_samples}")
        lines.append("")

        # Summary Statistics
        lines.append("## Summary Statistics")
        lines.append("")
        if summary:
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            for key in [
                "avg_faithfulness", "avg_hallucination_rate", "avg_recall_at_5",
                "avg_mrr", "avg_citation_coverage", "avg_latency_ms",
                "avg_total_tokens", "avg_answer_length", "avg_retrieved_chunks",
                "avg_prompt_tokens", "avg_completion_tokens",
            ]:
                if key in summary:
                    display_name = key.replace("avg_", "Avg ").replace("_", " ").title()
                    lines.append(f"| {display_name} | {summary[key]} |")
            lines.append("")

        # Retrieval Metrics
        if report.overall_retrieval_metrics:
            lines.append("## Retrieval Metrics")
            lines.append("")
            lines.append("| Metric | Mean | Std | Min | Max | P50 | P90 |")
            lines.append("|--------|------|-----|-----|-----|-----|-----|")
            for m in report.overall_retrieval_metrics:
                lines.append(
                    f"| {m.metric_name} | {m.mean:.4f} | {m.std:.4f} | "
                    f"{m.min_val:.4f} | {m.max_val:.4f} | {m.p50:.4f} | {m.p90:.4f} |"
                )
            lines.append("")

        # Generation Metrics
        if report.overall_generation_metrics:
            lines.append("## Generation Metrics")
            lines.append("")
            lines.append("| Metric | Mean | Std | Min | Max | P50 | P90 |")
            lines.append("|--------|------|-----|-----|-----|-----|-----|")
            for m in report.overall_generation_metrics:
                lines.append(
                    f"| {m.metric_name} | {m.mean:.4f} | {m.std:.4f} | "
                    f"{m.min_val:.4f} | {m.max_val:.4f} | {m.p50:.4f} | {m.p90:.4f} |"
                )
            lines.append("")

        # Category Breakdown
        _append_category_breakdown(lines, report.results)

        # Difficulty Breakdown
        _append_difficulty_breakdown(lines, report.results)

        # Top Failed Questions
        _append_failure_cases(lines, report.results)

        # Most Frequently Missed Documents
        _append_missed_documents(lines, report.results)

        return "\n".join(lines)

    @staticmethod
    def generate_benchmark_markdown(benchmark: BenchmarkResult) -> str:
        """Generate a comprehensive Markdown benchmark comparison report.

        Args:
            benchmark: Benchmark result to render.

        Returns:
            Markdown formatted string.
        """
        lines: list[str] = []

        lines.append("# RAG Provider Benchmark Report")
        lines.append("")
        lines.append(f"**Benchmark ID:** `{benchmark.benchmark_id}`")
        lines.append(f"**Dataset:** {benchmark.dataset_name}")
        lines.append(f"**Total Samples:** {benchmark.total_samples}")
        lines.append(f"**Providers Evaluated:** {len(benchmark.providers)}")
        lines.append(f"**Created:** {benchmark.created_at.isoformat()}")
        lines.append("")

        # Leaderboard
        if benchmark.leaderboard:
            lines.append("## Provider Leaderboard")
            lines.append("")
            lines.append(
                "| Rank | Provider | Model | Composite | Faithfulness | "
                "Hallucination | Citation Cov. | Recall@5 | Latency (ms) |"
            )
            lines.append(
                "|------|----------|-------|-----------|--------------|"
                "---------------|---------------|----------|--------------|"
            )
            for entry in benchmark.leaderboard:
                lines.append(
                    f"| {entry.get('rank', '-')} | {entry.get('provider', '-')} | "
                    f"{entry.get('model', '-')} | "
                    f"{entry.get('composite_score', 0.0):.4f} | "
                    f"{entry.get('avg_faithfulness', 0.0):.4f} | "
                    f"{entry.get('avg_hallucination_rate', 0.0):.4f} | "
                    f"{entry.get('avg_citation_coverage', 0.0):.4f} | "
                    f"{entry.get('avg_recall_at_5', 0.0):.4f} | "
                    f"{entry.get('avg_latency_ms', 0.0):.1f} |"
                )
            lines.append("")

        # Detailed Provider Comparison
        if benchmark.providers:
            lines.append("## Detailed Provider Comparison")
            lines.append("")
            lines.append(
                "| Provider | Samples | Success | Avg Tokens | "
                "Avg Answer Len | Avg Relevancy | Context Util. |"
            )
            lines.append(
                "|----------|---------|---------|------------|"
                "----------------|---------------|---------------|"
            )
            for p in benchmark.providers:
                lines.append(
                    f"| {p.provider_name} | {p.total_samples} | "
                    f"{p.successful_samples} | {p.avg_token_usage:.1f} | "
                    f"{p.avg_answer_length:.1f} | {p.avg_answer_relevancy:.4f} | "
                    f"{p.avg_context_utilization:.4f} |"
                )
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def generate_summary_stats(
        results: list[EvaluationResult],
    ) -> list[OverallMetrics]:
        """Compute summary statistics from a list of evaluation results.

        Args:
            results: List of evaluation results.

        Returns:
            List of OverallMetrics for key metrics.
        """
        successful = [r for r in results if r.success]
        if not successful:
            return []

        key_metrics: dict[str, list[float]] = {
            "faithfulness": [r.generation_metrics.faithfulness for r in successful],
            "hallucination_rate": [r.generation_metrics.hallucination_rate for r in successful],
            "recall_at_5": [r.retrieval_metrics.recall_at_5 for r in successful],
            "mrr": [r.retrieval_metrics.mrr for r in successful],
            "citation_coverage": [r.generation_metrics.citation_coverage for r in successful],
            "answer_relevancy": [r.generation_metrics.answer_relevancy for r in successful],
            "overall_response_time_ms": [r.generation_metrics.overall_response_time_ms for r in successful],
            "total_tokens": [float(r.generation_metrics.total_tokens) for r in successful],
        }

        overall: list[OverallMetrics] = []
        for name, values in key_metrics.items():
            stats = compute_overall_stats(values, name)
            overall.append(OverallMetrics(**stats))
        return overall


def _append_category_breakdown(
    lines: list[str],
    results: list[EvaluationResult],
) -> None:
    """Append category breakdown table to report lines."""
    successful = [r for r in results if r.success]
    if not successful:
        return

    categories: dict[str, list[EvaluationResult]] = {}
    for r in successful:
        # Extract category from metadata or use "general"
        cat = r.metadata.get("category", "general") if r.metadata else "general"
        categories.setdefault(cat, []).append(r)

    if len(categories) <= 1:
        return

    lines.append("## Category Breakdown")
    lines.append("")
    lines.append("| Category | Samples | Avg Faithfulness | Avg Recall@5 | Avg Latency (ms) |")
    lines.append("|----------|---------|------------------|--------------|-------------------|")
    for cat, cat_results in sorted(categories.items()):
        n = len(cat_results)
        avg_faith = sum(r.generation_metrics.faithfulness for r in cat_results) / n
        avg_recall = sum(r.retrieval_metrics.recall_at_5 for r in cat_results) / n
        avg_latency = sum(r.generation_metrics.overall_response_time_ms for r in cat_results) / n
        lines.append(f"| {cat} | {n} | {avg_faith:.4f} | {avg_recall:.4f} | {avg_latency:.1f} |")
    lines.append("")


def _append_difficulty_breakdown(
    lines: list[str],
    results: list[EvaluationResult],
) -> None:
    """Append difficulty breakdown table to report lines."""
    successful = [r for r in results if r.success]
    if not successful:
        return

    difficulties: dict[str, list[EvaluationResult]] = {}
    for r in successful:
        diff = r.metadata.get("difficulty", "medium") if r.metadata else "medium"
        difficulties.setdefault(diff, []).append(r)

    if len(difficulties) <= 1:
        return

    lines.append("## Difficulty Breakdown")
    lines.append("")
    lines.append("| Difficulty | Samples | Avg Faithfulness | Avg Recall@5 | Avg Latency (ms) |")
    lines.append("|------------|---------|------------------|--------------|-------------------|")
    for diff, diff_results in sorted(difficulties.items()):
        n = len(diff_results)
        avg_faith = sum(r.generation_metrics.faithfulness for r in diff_results) / n
        avg_recall = sum(r.retrieval_metrics.recall_at_5 for r in diff_results) / n
        avg_latency = sum(r.generation_metrics.overall_response_time_ms for r in diff_results) / n
        lines.append(f"| {diff} | {n} | {avg_faith:.4f} | {avg_recall:.4f} | {avg_latency:.1f} |")
    lines.append("")


def _append_failure_cases(
    lines: list[str],
    results: list[EvaluationResult],
    max_cases: int = 20,
) -> None:
    """Append top failure cases to report lines."""
    failed = [r for r in results if not r.success]
    if not failed:
        return

    lines.append(f"## Top {min(max_cases, len(failed))} Failed Questions")
    lines.append("")
    lines.append("| # | Question | Error |")
    lines.append("|---|----------|-------|")
    for i, r in enumerate(failed[:max_cases], start=1):
        question = r.question[:80].replace("|", "\\|")
        error = (r.error_message or "Unknown")[:60].replace("|", "\\|")
        lines.append(f"| {i} | {question} | {error} |")
    lines.append("")


def _append_missed_documents(
    lines: list[str],
    results: list[EvaluationResult],
    max_docs: int = 10,
) -> None:
    """Append most frequently missed documents to report lines."""
    missed_counts: dict[str, int] = {}
    for r in results:
        if not r.success:
            continue
        # Use raw trace to find expected vs retrieved
        expected = set(r.raw_trace.retrieved_chunk_ids) if r.raw_trace else set()
        # This is a simplified view — in production, compare expected_documents vs retrieved
        if r.retrieval_metrics.recall_at_5 < 1.0 and r.metadata:
            for doc_id in r.metadata.get("expected_documents", []):
                if doc_id not in expected:
                    missed_counts[doc_id] = missed_counts.get(doc_id, 0) + 1

    if not missed_counts:
        return

    sorted_missed = sorted(missed_counts.items(), key=lambda x: x[1], reverse=True)

    lines.append(f"## Most Frequently Missed Documents (Top {min(max_docs, len(sorted_missed))})")
    lines.append("")
    lines.append("| Document ID | Miss Count |")
    lines.append("|-------------|------------|")
    for doc_id, count in sorted_missed[:max_docs]:
        lines.append(f"| {doc_id[:40]} | {count} |")
    lines.append("")
