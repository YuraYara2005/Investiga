"""Evaluation Exporters for JSON, CSV, Markdown, and Excel Formats.

Provides serialization of evaluation reports and benchmark results to multiple
output formats for archival, dashboarding, and notebook consumption.
Excel export requires openpyxl (optional dependency with graceful fallback).
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.evaluation.models import (
    BenchmarkResult,
    EvaluationReport,
    EvaluationResult,
)
from app.evaluation.reports import ReportGenerator

logger = get_logger(__name__)


class EvaluationExporter:
    """Export evaluation reports and benchmark results to multiple formats."""

    @staticmethod
    def to_json(
        report: EvaluationReport,
        path: str | Path | None = None,
    ) -> str:
        """Export evaluation report as JSON string.

        Args:
            report: Evaluation report to export.
            path: Optional file path to save JSON.

        Returns:
            JSON string.
        """
        data = report.model_dump(mode="json")
        json_str = json.dumps(data, indent=2, default=str)
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json_str, encoding="utf-8")
            logger.info("report_exported", format="json", path=str(path))
        return json_str

    @staticmethod
    def to_csv(
        report: EvaluationReport,
        path: str | Path | None = None,
    ) -> str:
        """Export evaluation results as CSV string.

        Each row represents one evaluated sample with key metrics.

        Args:
            report: Evaluation report to export.
            path: Optional file path to save CSV.

        Returns:
            CSV string.
        """
        output = io.StringIO()
        fieldnames = [
            "sample_id", "question", "success", "provider", "model",
            "faithfulness", "hallucination_rate", "answer_relevancy",
            "citation_coverage", "citation_precision", "context_utilization",
            "recall_at_1", "recall_at_5", "mrr", "ndcg",
            "answer_length", "word_count",
            "prompt_tokens", "completion_tokens", "total_tokens",
            "llm_latency_ms", "overall_response_time_ms",
            "retrieved_chunks", "used_chunks", "citations_count",
            "error_message",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for r in report.results:
            writer.writerow(_result_to_csv_row(r))

        csv_str = output.getvalue()
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(csv_str, encoding="utf-8")
            logger.info("report_exported", format="csv", path=str(path))
        return csv_str

    @staticmethod
    def to_markdown(
        report: EvaluationReport,
        path: str | Path | None = None,
    ) -> str:
        """Export evaluation report as Markdown string.

        Args:
            report: Evaluation report to export.
            path: Optional file path to save Markdown.

        Returns:
            Markdown string.
        """
        md = ReportGenerator.generate_markdown(report)
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(md, encoding="utf-8")
            logger.info("report_exported", format="markdown", path=str(path))
        return md

    @staticmethod
    def to_excel(
        report: EvaluationReport,
        path: str | Path,
    ) -> bool:
        """Export evaluation report as Excel (.xlsx) file.

        Requires openpyxl. Returns False if openpyxl is not installed.

        Args:
            report: Evaluation report to export.
            path: File path to save Excel file.

        Returns:
            True if export succeeded, False if openpyxl unavailable.
        """
        try:
            import openpyxl  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("excel_export_skipped", reason="openpyxl not installed")
            return False

        wb = openpyxl.Workbook()
        ws = wb.active
        if ws is None:
            return False
        ws.title = "Evaluation Results"

        # Header row
        headers = [
            "Sample ID", "Question", "Success", "Provider", "Model",
            "Faithfulness", "Hallucination Rate", "Answer Relevancy",
            "Citation Coverage", "Citation Precision", "Context Utilization",
            "Recall@1", "Recall@5", "MRR", "nDCG",
            "Answer Length", "Word Count",
            "Prompt Tokens", "Completion Tokens", "Total Tokens",
            "LLM Latency (ms)", "Total Latency (ms)",
            "Retrieved Chunks", "Used Chunks", "Citations",
            "Error",
        ]
        ws.append(headers)

        # Data rows
        for r in report.results:
            ws.append([
                r.sample_id,
                r.question[:200],
                r.success,
                r.provider,
                r.model,
                r.generation_metrics.faithfulness,
                r.generation_metrics.hallucination_rate,
                r.generation_metrics.answer_relevancy,
                r.generation_metrics.citation_coverage,
                r.generation_metrics.citation_precision,
                r.generation_metrics.context_utilization,
                r.retrieval_metrics.recall_at_1,
                r.retrieval_metrics.recall_at_5,
                r.retrieval_metrics.mrr,
                r.retrieval_metrics.ndcg,
                r.generation_metrics.answer_length,
                r.generation_metrics.word_count,
                r.generation_metrics.prompt_tokens,
                r.generation_metrics.completion_tokens,
                r.generation_metrics.total_tokens,
                r.generation_metrics.llm_latency_ms,
                r.generation_metrics.overall_response_time_ms,
                r.retrieved_chunks_count,
                r.used_chunks_count,
                r.citations_count,
                r.error_message or "",
            ])

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        wb.save(str(path))
        logger.info("report_exported", format="excel", path=str(path))
        return True

    @staticmethod
    def export_benchmark(
        benchmark: BenchmarkResult,
        directory: str | Path,
    ) -> dict[str, str]:
        """Export all benchmark artifacts to a directory.

        Creates: benchmark.json, benchmark.csv, leaderboard.csv,
        provider_comparison.csv, benchmark.md

        Args:
            benchmark: Benchmark result to export.
            directory: Output directory path.

        Returns:
            Dictionary mapping artifact names to file paths.
        """
        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)
        artifacts: dict[str, str] = {}

        # JSON
        json_path = dir_path / "benchmark.json"
        json_str = json.dumps(benchmark.model_dump(mode="json"), indent=2, default=str)
        json_path.write_text(json_str, encoding="utf-8")
        artifacts["benchmark.json"] = str(json_path)

        # Markdown
        md_path = dir_path / "benchmark.md"
        md = ReportGenerator.generate_benchmark_markdown(benchmark)
        md_path.write_text(md, encoding="utf-8")
        artifacts["benchmark.md"] = str(md_path)

        # Leaderboard CSV
        if benchmark.leaderboard:
            lb_path = dir_path / "leaderboard.csv"
            _write_dict_list_csv(benchmark.leaderboard, lb_path)
            artifacts["leaderboard.csv"] = str(lb_path)

        # Provider comparison CSV
        if benchmark.providers:
            pc_path = dir_path / "provider_comparison.csv"
            rows = []
            for p in benchmark.providers:
                rows.append({
                    "provider": p.provider_name,
                    "model": p.model_name,
                    "samples": p.total_samples,
                    "successful": p.successful_samples,
                    "avg_latency_ms": p.avg_latency_ms,
                    "avg_faithfulness": p.avg_faithfulness,
                    "avg_hallucination_rate": p.avg_hallucination_rate,
                    "avg_citation_coverage": p.avg_citation_coverage,
                    "avg_recall_at_5": p.avg_recall_at_5,
                    "avg_mrr": p.avg_mrr,
                    "avg_token_usage": p.avg_token_usage,
                    "avg_answer_length": p.avg_answer_length,
                    "composite_score": p.composite_score,
                })
            _write_dict_list_csv(rows, pc_path)
            artifacts["provider_comparison.csv"] = str(pc_path)

        logger.info(
            "benchmark_exported",
            directory=str(dir_path),
            artifacts=list(artifacts.keys()),
        )
        return artifacts


def _result_to_csv_row(r: EvaluationResult) -> dict[str, Any]:
    """Convert an EvaluationResult to a flat CSV row dictionary."""
    return {
        "sample_id": r.sample_id,
        "question": r.question[:200],
        "success": r.success,
        "provider": r.provider,
        "model": r.model,
        "faithfulness": r.generation_metrics.faithfulness,
        "hallucination_rate": r.generation_metrics.hallucination_rate,
        "answer_relevancy": r.generation_metrics.answer_relevancy,
        "citation_coverage": r.generation_metrics.citation_coverage,
        "citation_precision": r.generation_metrics.citation_precision,
        "context_utilization": r.generation_metrics.context_utilization,
        "recall_at_1": r.retrieval_metrics.recall_at_1,
        "recall_at_5": r.retrieval_metrics.recall_at_5,
        "mrr": r.retrieval_metrics.mrr,
        "ndcg": r.retrieval_metrics.ndcg,
        "answer_length": r.generation_metrics.answer_length,
        "word_count": r.generation_metrics.word_count,
        "prompt_tokens": r.generation_metrics.prompt_tokens,
        "completion_tokens": r.generation_metrics.completion_tokens,
        "total_tokens": r.generation_metrics.total_tokens,
        "llm_latency_ms": r.generation_metrics.llm_latency_ms,
        "overall_response_time_ms": r.generation_metrics.overall_response_time_ms,
        "retrieved_chunks": r.retrieved_chunks_count,
        "used_chunks": r.used_chunks_count,
        "citations_count": r.citations_count,
        "error_message": r.error_message or "",
    }


def _write_dict_list_csv(
    data: list[dict[str, Any]],
    path: Path,
) -> None:
    """Write a list of dictionaries to a CSV file."""
    if not data:
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(data[0].keys()))
        writer.writeheader()
        writer.writerows(data)
