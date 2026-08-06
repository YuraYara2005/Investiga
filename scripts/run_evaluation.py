#!/usr/bin/env python3
"""Investiga Evaluation Runner CLI.

Executes the RAG Evaluation Framework against benchmark datasets, computes
retrieval and generation metrics, builds notebook-ready DataFrames, and exports
reports in Markdown, JSON, CSV, and Excel formats.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Bootstrap Python path for direct execution
_SCRIPTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPTS_DIR.parent
_BACKEND_DIR = _REPO_ROOT / "backend"
for _p in [str(_REPO_ROOT), str(_BACKEND_DIR), str(_SCRIPTS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts.common.helpers import bootstrap_environment

bootstrap_environment()
# pyrefly: ignore [missing-import]
from app.core.logging import get_logger
# pyrefly: ignore [missing-import]
from app.evaluation.analytics import EvaluationDataFrameBuilder
# pyrefly: ignore [missing-import]
from app.evaluation.dataset import DatasetLoader
# pyrefly: ignore [missing-import]
from app.evaluation.exporters import EvaluationExporter
# pyrefly: ignore [missing-import]
from app.evaluation.models import (
    EvaluationConfiguration,
    EvaluationReport,
    EvaluationSample,
    OverallMetrics,
)
from rich.table import Table

from scripts.common.console import (
    create_progress,
    get_console,
    print_banner,
    print_error,
    print_info,
    print_key_values,
    print_section,
    print_success,
    print_warning,
    setup_signal_handling,
)
from scripts.common.factory import (
    create_cli_evaluator,
    create_cli_rag_service,
)
from scripts.common.helpers import (
    format_duration,
    format_ms,
    format_pct,
    format_score,
    resolve_path,
)

logger = get_logger(__name__)

SUPPORTED_PROVIDERS = ["gemini", "ollama", "mock"]


def build_parser() -> argparse.ArgumentParser:
    """Construct argument parser for evaluation execution."""
    parser = argparse.ArgumentParser(
        prog="investiga-evaluate",
        description="Execute the Investiga RAG Evaluation Framework against benchmark datasets.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dataset",
        "-d",
        type=str,
        default=None,
        help="Path to evaluation dataset file (.json, .jsonl, or .csv).",
    )
    parser.add_argument(
        "--provider",
        "-p",
        type=str,
        default="mock",
        choices=SUPPORTED_PROVIDERS,
        help="LLM provider to evaluate.",
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="Model name override.",
    )
    parser.add_argument(
        "--strategy",
        "-s",
        type=str,
        default="standard_qa",
        help="Prompt synthesis strategy.",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help="Output directory for generated reports and artifacts.",
    )
    parser.add_argument(
        "--k-values",
        "-k",
        type=str,
        default="1,3,5,10",
        help="Comma-separated list of K values for retrieval recall/precision metrics.",
    )
    parser.add_argument(
        "--concurrency",
        "-c",
        type=int,
        default=4,
        help="Maximum concurrent evaluation tasks.",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=float,
        default=60.0,
        help="Timeout per evaluation sample in seconds.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Enable verbose evaluation telemetry.",
    )
    return parser


def _get_default_benchmark_samples() -> list[EvaluationSample]:
    """Generate default benchmark test samples when no dataset file is provided."""
    return [
        EvaluationSample(
            sample_id="eval-001",
            question="What is the architecture and primary purpose of Investiga?",
            expected_answer="Investiga is an enterprise incident investigation and knowledge platform.",
            expected_keywords=["incident", "investigation", "platform", "enterprise"],
            difficulty="easy",
            category="architecture",
        ),
        EvaluationSample(
            sample_id="eval-002",
            question="How does hybrid retrieval combine dense vectors and sparse keywords?",
            expected_answer="Hybrid retrieval merges dense vector similarity scores and sparse keyword BM25 scores using Reciprocal Rank Fusion (RRF).",
            expected_keywords=["dense", "sparse", "vector", "hybrid", "retrieval", "fusion"],
            difficulty="medium",
            category="retrieval",
        ),
        EvaluationSample(
            sample_id="eval-003",
            question="How are document chunks embedded and persisted in Qdrant and relational storage?",
            expected_answer="Document chunks are vectorized with SentenceTransformers, upserted into Qdrant collections with metadata payloads, and persisted to relational KnowledgeChunk tables.",
            expected_keywords=["chunk", "embedding", "qdrant", "vector", "persistence"],
            difficulty="hard",
            category="ingestion",
        ),
        EvaluationSample(
            sample_id="eval-004",
            question="What guardrail checks are applied to generated RAG answers?",
            expected_answer="RAG answers undergo hallucination detection, citation verification, and faithfulness guardrails.",
            expected_keywords=["guardrail", "citation", "faithfulness", "hallucination"],
            difficulty="medium",
            category="rag",
        ),
    ]


def _parse_k_values(val: str) -> list[int]:
    """Parse comma-separated K values."""
    try:
        return [int(x.strip()) for x in val.split(",") if x.strip()]
    except ValueError:
        return [1, 3, 5, 10]


def _find_metric(metrics: list[OverallMetrics], name: str) -> OverallMetrics | None:
    """Find metric container by name."""
    for m in metrics:
        if m.metric_name == name:
            return m
    return None


def _export_report_artifacts(
    report: EvaluationReport,
    output_dir: Path,
) -> dict[str, str]:
    """Export evaluation report to JSON, Markdown, CSV, Excel, and Traces."""
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}

    # 1. JSON
    json_path = output_dir / "report.json"
    EvaluationExporter.to_json(report, json_path)
    artifacts["report.json"] = str(json_path)

    # 2. Markdown
    md_path = output_dir / "report.md"
    EvaluationExporter.to_markdown(report, md_path)
    artifacts["report.md"] = str(md_path)

    # 3. CSV
    csv_path = output_dir / "report.csv"
    EvaluationExporter.to_csv(report, csv_path)
    artifacts["report.csv"] = str(csv_path)

    # 4. Excel (.xlsx)
    xlsx_path = output_dir / "report.xlsx"
    excel_ok = EvaluationExporter.to_excel(report, xlsx_path)
    if excel_ok:
        artifacts["report.xlsx"] = str(xlsx_path)

    # 5. Leaderboard / Provider comparison CSV
    lb_path = output_dir / "leaderboard.csv"
    m_faith = _find_metric(report.overall_generation_metrics, "faithfulness")
    m_halluc = _find_metric(report.overall_generation_metrics, "hallucination_rate")
    m_cit = _find_metric(report.overall_generation_metrics, "citation_coverage")
    m_rec5 = _find_metric(report.overall_retrieval_metrics, "recall_at_5")
    m_mrr = _find_metric(report.overall_retrieval_metrics, "mrr")
    m_lat = _find_metric(report.overall_generation_metrics, "llm_latency_ms")

    success_rate = (
        report.run_metadata.successful_samples / max(1, report.run_metadata.total_samples)
    )

    lb_rows = [
        {
            "rank": 1,
            "provider": report.run_metadata.provider or "unknown",
            "model": report.configuration.model_override or "default",
            "samples": report.run_metadata.total_samples,
            "success_rate": round(success_rate, 4),
            "faithfulness": round(m_faith.mean, 4) if m_faith else 0.0,
            "hallucination_rate": round(m_halluc.mean, 4) if m_halluc else 0.0,
            "citation_coverage": round(m_cit.mean, 4) if m_cit else 0.0,
            "recall_at_5": round(m_rec5.mean, 4) if m_rec5 else 0.0,
            "mrr": round(m_mrr.mean, 4) if m_mrr else 0.0,
            "avg_latency_ms": round(m_lat.mean, 2) if m_lat else 0.0,
        }
    ]
    with open(lb_path, "w", encoding="utf-8", newline="") as f:
        import csv
        writer = csv.DictWriter(f, fieldnames=list(lb_rows[0].keys()))
        writer.writeheader()
        writer.writerows(lb_rows)
    artifacts["leaderboard.csv"] = str(lb_path)

    pc_path = output_dir / "provider_comparison.csv"
    with open(pc_path, "w", encoding="utf-8", newline="") as f:
        import csv
        writer = csv.DictWriter(f, fieldnames=list(lb_rows[0].keys()))
        writer.writeheader()
        writer.writerows(lb_rows)
    artifacts["provider_comparison.csv"] = str(pc_path)

    # 6. Traces JSON
    trace_path = output_dir / "trace.json"
    traces = [
        {
            "sample_id": r.sample_id,
            "question": r.question,
            "expected_answer": r.expected_answer,
            "generated_answer": r.generated_answer,
            "success": r.success,
            "retrieved_chunks": r.retrieved_chunks_count,
            "used_chunks": r.used_chunks_count,
            "citations": r.citations_count,
            "generation_metrics": r.generation_metrics.model_dump(),
            "retrieval_metrics": r.retrieval_metrics.model_dump(),
            "error": r.error_message,
        }
        for r in report.results
    ]
    trace_path.write_text(json.dumps(traces, indent=2, default=str), encoding="utf-8")
    artifacts["trace.json"] = str(trace_path)

    return artifacts


async def run_evaluation(args: argparse.Namespace) -> int:
    """Execute evaluation run and output results."""
    console = get_console()
    timestamp_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out_dir_path = resolve_path(args.output_dir or f"evaluation_runs/run_{timestamp_str}")

    print_banner(
        title="RAG Evaluation Framework Runner",
        subtitle=f"Evaluating Provider: {args.provider.upper()}",
    )

    # 1. Load samples
    samples: list[EvaluationSample] = []
    if args.dataset:
        dataset_path = resolve_path(args.dataset)
        if not dataset_path.exists():
            print_error(f"Dataset file not found: {dataset_path}")
            return 1

        ext = dataset_path.suffix.lower()
        try:
            if ext == ".json":
                samples = DatasetLoader.load_json(dataset_path)
            elif ext == ".jsonl":
                samples = DatasetLoader.load_jsonl(dataset_path)
            elif ext == ".csv":
                samples = DatasetLoader.load_csv(dataset_path)
            else:
                samples = DatasetLoader.load_json(dataset_path)
        except Exception as exc:  # noqa: BLE001
            print_error(f"Failed to load dataset '{dataset_path}': {exc}", exc=exc)
            return 1
    else:
        print_info("No dataset specified (--dataset). Using default benchmark sample suite.")
        samples = _get_default_benchmark_samples()

    if not samples:
        print_error("Dataset contains 0 evaluation samples.")
        return 1

    k_vals = _parse_k_values(args.k_values)
    config = EvaluationConfiguration(
        k_values=k_vals,
        max_concurrency=args.concurrency,
        timeout_seconds=args.timeout,
        provider_override=args.provider,
        model_override=args.model,
        prompt_strategy=args.strategy,
        dataset_name=str(args.dataset or "builtin_benchmark"),
    )

    print_key_values(
        {
            "Dataset Source": str(args.dataset or "Builtin Benchmark Suite"),
            "Sample Count": len(samples),
            "LLM Provider": args.provider,
            "Model Override": args.model or "Default",
            "Strategy": args.strategy,
            "K Values": ", ".join(str(k) for k in k_vals),
            "Concurrency": args.concurrency,
            "Output Directory": str(out_dir_path),
        },
        title="Evaluation Run Parameters",
    )

    _cancel_event = setup_signal_handling()

    # 2. Initialize RAG Evaluator
    rag_service = create_cli_rag_service()
    evaluator = create_cli_evaluator(rag_service=rag_service)

    start_time = time.perf_counter()
    report: EvaluationReport | None = None

    with create_progress() as progress:
        task_id = progress.add_task(
            f"[cyan]Evaluating {len(samples)} samples on {args.provider}...",
            total=len(samples),
        )

        def on_progress(completed: int, total: int, sample_id: str) -> None:
            progress.update(task_id, completed=completed)

        try:
            # Execute evaluation
            report = await evaluator.evaluate_dataset(
                samples=samples,
                config=config,
                progress_callback=on_progress,
            )
            progress.update(task_id, completed=len(samples))
        except (KeyboardInterrupt, asyncio.CancelledError):
            print_warning("\nEvaluation interrupted by user.")
            return 130
        except Exception as exc:  # noqa: BLE001
            print_error(f"Evaluation failed: {exc}", exc=exc)
            return 1

    elapsed_time = time.perf_counter() - start_time

    # 3. Export Artifacts
    artifacts = _export_report_artifacts(report, out_dir_path)

    # 4. Build Analytics DataFrame (validating analytics layer integration)
    try:
        _ = EvaluationDataFrameBuilder.results_to_dataframe(report.results)
    except Exception as exc:  # noqa: BLE001
        logger.warning("dataframe_build_warning", error=str(exc))

    # 5. Render Professional Summary Tables
    print_section("Retrieval Quality Metrics")
    ret_table = Table(
        title="Hybrid Retrieval Performance Breakdown",
        border_style="bright_blue",
        header_style="bold cyan",
    )
    ret_table.add_column("Metric", style="bold white")
    ret_table.add_column("Mean Score", justify="right", style="bold bright_cyan")
    ret_table.add_column("p90", justify="right", style="cyan")
    ret_table.add_column("Description", style="dim white")

    ret_metrics_defs = [
        ("recall_at_1", "Recall@1", "Relevant chunk ranked 1st", True),
        ("recall_at_3", "Recall@3", "Relevant chunk in top 3", True),
        ("recall_at_5", "Recall@5", "Relevant chunk in top 5", True),
        ("recall_at_10", "Recall@10", "Relevant chunk in top 10", True),
        ("mrr", "MRR", "Mean Reciprocal Rank of first relevant chunk", False),
        ("map_score", "MAP", "Mean Average Precision across all chunks", False),
        ("ndcg", "nDCG", "Normalized Discounted Cumulative Gain", False),
        ("hit_rate", "Hit Rate", "Fraction of queries with >=1 hit", True),
    ]

    for key, label, desc, is_pct in ret_metrics_defs:
        m = _find_metric(report.overall_retrieval_metrics, key)
        if m:
            mean_str = format_pct(m.mean) if is_pct else format_score(m.mean)
            p90_str = format_pct(m.p90) if is_pct else format_score(m.p90)
            ret_table.add_row(label, mean_str, p90_str, desc)

    console.print(ret_table)

    print_section("Generation & Safety Metrics")
    gen_table = Table(
        title="RAG Generation Fidelity and Guardrail Performance",
        border_style="bright_blue",
        header_style="bold cyan",
    )
    gen_table.add_column("Metric", style="bold white")
    gen_table.add_column("Mean Score", justify="right", style="bold bright_cyan")
    gen_table.add_column("p90", justify="right", style="cyan")
    gen_table.add_column("Target / Note", style="dim white")

    gen_metrics_defs = [
        ("faithfulness", "Faithfulness", "Claim overlap with retrieved context", True),
        ("citation_coverage", "Citation Coverage", "Statements supported by citations", True),
        ("citation_precision", "Citation Precision", "Citations accurately matched", True),
        ("hallucination_rate", "Hallucination Rate", "Unsubstantiated claims (lower is better)", True),
        ("answer_relevancy", "Answer Relevancy", "Relevance to original question", True),
        ("context_utilization", "Context Utilization", "Efficiency of context window usage", True),
    ]

    for key, label, desc, is_pct in gen_metrics_defs:
        m = _find_metric(report.overall_generation_metrics, key)
        if m:
            mean_str = format_pct(m.mean) if is_pct else format_score(m.mean)
            p90_str = format_pct(m.p90) if is_pct else format_score(m.p90)
            gen_table.add_row(label, mean_str, p90_str, desc)

    console.print(gen_table)

    print_section("Performance & Latency Telemetry")
    perf_table = Table(
        title="Inference & Execution Latency",
        border_style="bright_blue",
        header_style="bold cyan",
    )
    perf_table.add_column("Metric", style="bold white")
    perf_table.add_column("Average", justify="right", style="bold bright_cyan")
    perf_table.add_column("p90 Latency", justify="right", style="cyan")
    perf_table.add_column("p99 Latency", justify="right", style="dim cyan")

    m_llm_lat = _find_metric(report.overall_generation_metrics, "llm_latency_ms")
    m_tot_lat = _find_metric(report.overall_generation_metrics, "overall_response_time_ms")
    m_prompt_tok = _find_metric(report.overall_generation_metrics, "prompt_tokens")
    m_comp_tok = _find_metric(report.overall_generation_metrics, "completion_tokens")
    m_tot_tok = _find_metric(report.overall_generation_metrics, "total_tokens")

    if m_llm_lat:
        perf_table.add_row(
            "LLM Generation Latency",
            format_ms(m_llm_lat.mean),
            format_ms(m_llm_lat.p90),
            format_ms(m_llm_lat.p99),
        )
    if m_tot_lat:
        perf_table.add_row(
            "Total Response Time",
            format_ms(m_tot_lat.mean),
            format_ms(m_tot_lat.p90),
            format_ms(m_tot_lat.p99),
        )
    if m_tot_tok:
        perf_table.add_row(
            "Token Usage",
            f"{m_tot_tok.mean:.0f} tokens",
            f"Prompt: {m_prompt_tok.mean:.0f}" if m_prompt_tok else "-",
            f"Completion: {m_comp_tok.mean:.0f}" if m_comp_tok else "-",
        )

    console.print(perf_table)

    print_section("Generated Artifacts")
    print_key_values(
        {k: str(v) for k, v in artifacts.items()},
        title="Saved Reports & Exports",
    )

    success_pct = (
        (report.run_metadata.successful_samples / max(1, report.run_metadata.total_samples)) * 100.0
    )
    print_success(
        f"Evaluation completed in {format_duration(elapsed_time)} "
        f"({report.run_metadata.successful_samples}/{report.run_metadata.total_samples} successful, {success_pct:.1f}% success rate)."
    )
    return 0


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.verbose:
        os.environ["INVESTIGA_VERBOSE"] = "1"

    try:
        exit_code = asyncio.run(run_evaluation(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        get_console().print("\n[warning]Operation interrupted.[/warning]")
        sys.exit(130)


if __name__ == "__main__":
    main()
