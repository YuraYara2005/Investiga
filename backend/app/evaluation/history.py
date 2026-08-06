"""Evaluation History, Trace Viewer, and Experiment Comparison.

Provides persistent storage for evaluation runs under evaluation_runs/,
a TraceViewer for debugging individual benchmark questions, and
compare_runs() for comparing multiple evaluation experiments across
providers, prompt strategies, and retrieval configurations.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.evaluation.exporters import EvaluationExporter
from app.evaluation.models import (
    BenchmarkResult,
    EvaluationReport,
    EvaluationResult,
)

logger = get_logger(__name__)

DEFAULT_BASE_DIR = "evaluation_runs"


class EvaluationHistory:
    """Persistent storage and retrieval of evaluation runs.

    Stores all evaluation artifacts under a timestamped directory for
    reproducibility and experiment tracking.

    Args:
        base_dir: Root directory for evaluation run storage.
    """

    def __init__(self, base_dir: str | Path = DEFAULT_BASE_DIR) -> None:
        self._base_dir = Path(base_dir)

    @property
    def base_dir(self) -> Path:
        """Root directory for evaluation runs."""
        return self._base_dir

    def save_run(
        self,
        report: EvaluationReport,
        benchmark: BenchmarkResult | None = None,
    ) -> Path:
        """Save an evaluation run with all artifacts.

        Creates a timestamped directory containing:
        - report.md
        - report.json
        - metrics.csv
        - metrics.xlsx (if openpyxl available)
        - trace.json
        - benchmark.csv (if benchmark provided)
        - leaderboard.csv (if benchmark provided)
        - provider_comparison.csv (if benchmark provided)

        Args:
            report: Evaluation report to save.
            benchmark: Optional benchmark result to include.

        Returns:
            Path to the created run directory.
        """
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S_%f")
        run_dir = self._base_dir / timestamp
        run_dir.mkdir(parents=True, exist_ok=True)

        # Save report artifacts
        EvaluationExporter.to_markdown(report, run_dir / "report.md")
        EvaluationExporter.to_json(report, run_dir / "report.json")
        EvaluationExporter.to_csv(report, run_dir / "metrics.csv")
        EvaluationExporter.to_excel(report, run_dir / "metrics.xlsx")

        # Save raw traces
        traces = [r.raw_trace.model_dump(mode="json") for r in report.results if r.raw_trace]
        trace_path = run_dir / "trace.json"
        trace_path.write_text(json.dumps(traces, indent=2, default=str), encoding="utf-8")

        # Save run metadata
        meta_path = run_dir / "run_metadata.json"
        meta_path.write_text(
            json.dumps(report.run_metadata.model_dump(mode="json"), indent=2, default=str),
            encoding="utf-8",
        )

        # Save benchmark if provided
        if benchmark:
            EvaluationExporter.export_benchmark(benchmark, run_dir)

        logger.info(
            "evaluation_run_saved",
            run_dir=str(run_dir),
            total_samples=report.run_metadata.total_samples,
        )
        return run_dir

    def list_runs(self) -> list[dict[str, Any]]:
        """List all saved evaluation runs.

        Returns:
            List of run metadata dictionaries with run_id, path, and timestamp.
        """
        if not self._base_dir.exists():
            return []

        runs: list[dict[str, Any]] = []
        for run_dir in sorted(self._base_dir.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue
            meta_path = run_dir / "run_metadata.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    runs.append({
                        "run_id": meta.get("run_id", run_dir.name),
                        "path": str(run_dir),
                        "timestamp": run_dir.name,
                        "provider": meta.get("provider", "unknown"),
                        "dataset_name": meta.get("dataset_name", "unknown"),
                        "total_samples": meta.get("total_samples", 0),
                        "successful_samples": meta.get("successful_samples", 0),
                        "duration_seconds": meta.get("total_duration_seconds", 0.0),
                    })
                except (json.JSONDecodeError, OSError):
                    runs.append({
                        "run_id": run_dir.name,
                        "path": str(run_dir),
                        "timestamp": run_dir.name,
                    })
            else:
                runs.append({
                    "run_id": run_dir.name,
                    "path": str(run_dir),
                    "timestamp": run_dir.name,
                })
        return runs

    def load_run(self, run_id: str) -> EvaluationReport | None:
        """Load a saved evaluation report by run ID or timestamp directory name.

        Args:
            run_id: Run identifier (timestamp directory name or run UUID).

        Returns:
            EvaluationReport if found, None otherwise.
        """
        # Try direct path match
        run_dir = self._base_dir / run_id
        if not run_dir.exists():
            if not self._base_dir.exists():
                return None
            # Search by run_id in metadata
            for d in self._base_dir.iterdir():
                if not d.is_dir():
                    continue
                meta_path = d / "run_metadata.json"
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                        if meta.get("run_id") == run_id:
                            run_dir = d
                            break
                    except (json.JSONDecodeError, OSError):
                        continue
            else:
                return None

        report_path = run_dir / "report.json"
        if not report_path.exists():
            return None

        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
            return EvaluationReport(**data)
        except Exception as exc:
            logger.warning("failed_to_load_run", run_id=run_id, error=str(exc))
            return None


class TraceViewer:
    """Utility for viewing and debugging individual evaluation traces.

    Loads raw trace data from saved evaluation runs and exposes structured
    views for debugging failed benchmark questions.
    """

    def __init__(self, history: EvaluationHistory | None = None) -> None:
        self._history = history or EvaluationHistory()

    def view_trace(
        self,
        run_id: str,
        sample_id: str,
    ) -> dict[str, Any] | None:
        """View the complete trace for a specific evaluated question.

        Args:
            run_id: Evaluation run identifier.
            sample_id: Sample ID to view.

        Returns:
            Dictionary with question, chunks, prompt, answer, citations,
            metrics, and latency breakdown. None if not found.
        """
        report = self._history.load_run(run_id)
        if not report:
            return None

        for result in report.results:
            if result.sample_id == sample_id:
                return self._format_trace(result)

        return None

    def view_all_traces(self, run_id: str) -> list[dict[str, Any]]:
        """View traces for all questions in a run.

        Args:
            run_id: Evaluation run identifier.

        Returns:
            List of trace dictionaries.
        """
        report = self._history.load_run(run_id)
        if not report:
            return []

        return [self._format_trace(r) for r in report.results]

    def view_failures(self, run_id: str) -> list[dict[str, Any]]:
        """View traces for failed questions only.

        Args:
            run_id: Evaluation run identifier.

        Returns:
            List of failure trace dictionaries.
        """
        report = self._history.load_run(run_id)
        if not report:
            return []

        return [self._format_trace(r) for r in report.results if not r.success]

    @staticmethod
    def _format_trace(result: EvaluationResult) -> dict[str, Any]:
        """Format an EvaluationResult into a debug-friendly trace view.

        Args:
            result: Evaluation result to format.

        Returns:
            Structured trace dictionary.
        """
        trace = result.raw_trace
        return {
            "sample_id": result.sample_id,
            "question": result.question,
            "expected_answer": result.expected_answer,
            "generated_answer": result.generated_answer,
            "success": result.success,
            "error_message": result.error_message,
            "provider": trace.provider if trace else result.provider,
            "model": trace.model if trace else result.model,
            "retrieved_chunks": {
                "count": len(trace.retrieved_chunk_ids) if trace else 0,
                "ids": trace.retrieved_chunk_ids if trace else [],
                "scores": trace.retrieved_scores if trace else [],
                "texts": trace.retrieved_chunk_texts if trace else [],
            },
            "prompt": {
                "system": trace.prompt_system if trace else "",
                "user": trace.prompt_user if trace else "",
            },
            "citations": trace.extracted_citations if trace else [],
            "retrieval_metrics": {
                "recall_at_1": result.retrieval_metrics.recall_at_1,
                "recall_at_5": result.retrieval_metrics.recall_at_5,
                "mrr": result.retrieval_metrics.mrr,
                "ndcg": result.retrieval_metrics.ndcg,
                "context_precision": result.retrieval_metrics.context_precision,
                "context_recall": result.retrieval_metrics.context_recall,
            },
            "generation_metrics": {
                "faithfulness": result.generation_metrics.faithfulness,
                "hallucination_rate": result.generation_metrics.hallucination_rate,
                "answer_relevancy": result.generation_metrics.answer_relevancy,
                "citation_coverage": result.generation_metrics.citation_coverage,
                "citation_precision": result.generation_metrics.citation_precision,
                "context_utilization": result.generation_metrics.context_utilization,
            },
            "latency_breakdown": {
                "retrieval_ms": trace.retrieval_latency_ms if trace else 0.0,
                "context_build_ms": trace.context_build_latency_ms if trace else 0.0,
                "prompt_build_ms": trace.prompt_build_latency_ms if trace else 0.0,
                "llm_ms": trace.llm_latency_ms if trace else 0.0,
                "citation_ms": trace.citation_latency_ms if trace else 0.0,
                "total_ms": trace.total_latency_ms if trace else 0.0,
            },
        }


def compare_runs(
    history: EvaluationHistory,
    run_ids: list[str],
) -> dict[str, Any]:
    """Compare multiple evaluation runs side-by-side.

    Compares key metrics across runs including Recall, MRR, Faithfulness,
    Hallucination Rate, Latency, Provider, Prompt Strategy, and more.

    Args:
        history: EvaluationHistory instance.
        run_ids: List of run identifiers to compare.

    Returns:
        Comparison dictionary with per-run metrics and deltas.
    """
    comparisons: list[dict[str, Any]] = []

    for run_id in run_ids:
        report = history.load_run(run_id)
        if not report:
            comparisons.append({
                "run_id": run_id,
                "status": "not_found",
            })
            continue

        meta = report.run_metadata
        summary = report.summary

        comparisons.append({
            "run_id": run_id,
            "status": "loaded",
            "provider": meta.provider,
            "dataset_name": meta.dataset_name,
            "total_samples": meta.total_samples,
            "successful_samples": meta.successful_samples,
            "failed_samples": meta.failed_samples,
            "duration_seconds": meta.total_duration_seconds,
            "prompt_strategy": meta.configuration.prompt_strategy,
            "avg_recall_at_5": summary.get("avg_recall_at_5", 0.0),
            "avg_mrr": summary.get("avg_mrr", 0.0),
            "avg_faithfulness": summary.get("avg_faithfulness", 0.0),
            "avg_hallucination_rate": summary.get("avg_hallucination_rate", 0.0),
            "avg_latency_ms": summary.get("avg_latency_ms", 0.0),
            "avg_citation_coverage": summary.get("avg_citation_coverage", 0.0),
            "avg_total_tokens": summary.get("avg_total_tokens", 0.0),
            "avg_answer_length": summary.get("avg_answer_length", 0.0),
            "avg_retrieved_chunks": summary.get("avg_retrieved_chunks", 0.0),
            "avg_prompt_tokens": summary.get("avg_prompt_tokens", 0.0),
            "avg_completion_tokens": summary.get("avg_completion_tokens", 0.0),
        })

    # Compute deltas between consecutive runs
    deltas: list[dict[str, Any]] = []
    metric_keys = [
        "avg_recall_at_5", "avg_mrr", "avg_faithfulness",
        "avg_hallucination_rate", "avg_latency_ms", "avg_citation_coverage",
    ]
    for i in range(1, len(comparisons)):
        prev = comparisons[i - 1]
        curr = comparisons[i]
        if prev.get("status") != "loaded" or curr.get("status") != "loaded":
            continue
        delta: dict[str, Any] = {
            "from_run": prev["run_id"],
            "to_run": curr["run_id"],
        }
        for key in metric_keys:
            prev_val = prev.get(key, 0.0)
            curr_val = curr.get(key, 0.0)
            delta[f"{key}_delta"] = round(curr_val - prev_val, 4)
        deltas.append(delta)

    logger.info("runs_compared", run_count=len(run_ids), loaded=sum(1 for c in comparisons if c.get("status") == "loaded"))

    return {
        "runs": comparisons,
        "deltas": deltas,
        "total_compared": len(comparisons),
    }
