#!/usr/bin/env python3
"""Investiga Multi-Provider Benchmark CLI.

Benchmarks and compares multiple LLM providers (Gemini, Ollama, Mock) against
identical evaluation datasets, generates composite quality leaderboards, builds
analytics DataFrames, and exports comparison reports across multiple formats.
"""

from __future__ import annotations

import argparse
import asyncio
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
from app.evaluation.analytics import (
    LeaderboardFrame,
    ProviderComparisonFrame,
)
# pyrefly: ignore [missing-import]
from app.evaluation.dataset import DatasetLoader
# pyrefly: ignore [missing-import]
from app.evaluation.exporters import EvaluationExporter
# pyrefly: ignore [missing-import]
from app.evaluation.models import (
    BenchmarkResult,
    EvaluationConfiguration,
    EvaluationSample,
)
from rich.panel import Panel
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
    create_cli_benchmark,
)
from scripts.common.helpers import (
    format_duration,
    format_ms,
    format_pct,
    resolve_path,
)

logger = get_logger(__name__)

ALL_PROVIDERS = ["mock", "gemini", "ollama"]


def build_parser() -> argparse.ArgumentParser:
    """Construct argument parser for provider benchmarking."""
    parser = argparse.ArgumentParser(
        prog="investiga-benchmark",
        description="Benchmark and rank LLM providers for Investiga RAG.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dataset",
        "-d",
        type=str,
        default=None,
        help="Path to benchmark dataset file (.json, .jsonl, or .csv).",
    )
    parser.add_argument(
        "--providers",
        "-p",
        type=str,
        default="mock",
        help="Comma-separated providers to benchmark (e.g., 'mock,gemini,ollama' or 'all').",
    )
    parser.add_argument(
        "--strategy",
        "-s",
        type=str,
        default="standard_qa",
        help="Prompt synthesis strategy to benchmark.",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help="Output directory for generated benchmark artifacts.",
    )
    parser.add_argument(
        "--concurrency",
        "-c",
        type=int,
        default=4,
        help="Maximum concurrent evaluation tasks per provider.",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=float,
        default=60.0,
        help="Timeout per sample evaluation in seconds.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Enable verbose benchmark telemetry.",
    )
    return parser


def _get_default_benchmark_samples() -> list[EvaluationSample]:
    """Generate default benchmark test samples when no dataset file is provided."""
    return [
        EvaluationSample(
            sample_id="bench-001",
            question="What is the architecture and primary purpose of Investiga?",
            expected_answer="Investiga is an enterprise incident investigation and knowledge platform.",
            expected_keywords=["incident", "investigation", "platform", "enterprise"],
            difficulty="easy",
            category="architecture",
        ),
        EvaluationSample(
            sample_id="bench-002",
            question="How does hybrid retrieval combine dense vectors and sparse keywords?",
            expected_answer="Hybrid retrieval merges dense vector similarity scores and sparse keyword BM25 scores using Reciprocal Rank Fusion (RRF).",
            expected_keywords=["dense", "sparse", "vector", "hybrid", "retrieval", "fusion"],
            difficulty="medium",
            category="retrieval",
        ),
        EvaluationSample(
            sample_id="bench-003",
            question="How are document chunks embedded and persisted in Qdrant and relational storage?",
            expected_answer="Document chunks are vectorized with SentenceTransformers, upserted into Qdrant collections with metadata payloads, and persisted to relational KnowledgeChunk tables.",
            expected_keywords=["chunk", "embedding", "qdrant", "vector", "persistence"],
            difficulty="hard",
            category="ingestion",
        ),
        EvaluationSample(
            sample_id="bench-004",
            question="What guardrail checks are applied to generated RAG answers?",
            expected_answer="RAG answers undergo hallucination detection, citation verification, and faithfulness guardrails.",
            expected_keywords=["guardrail", "citation", "faithfulness", "hallucination"],
            difficulty="medium",
            category="rag",
        ),
    ]


def _parse_providers(prov_arg: str) -> list[str]:
    """Parse comma-separated provider argument into valid provider names."""
    if prov_arg.strip().lower() == "all":
        return ALL_PROVIDERS

    providers = []
    for item in prov_arg.split(","):
        p = item.strip().lower()
        if p and p in ALL_PROVIDERS and p not in providers:
            providers.append(p)
    return providers or ["mock"]


async def run_benchmark(args: argparse.Namespace) -> int:
    """Execute multi-provider benchmark and render leaderboard."""
    console = get_console()
    timestamp_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out_dir_path = resolve_path(args.output_dir or f"benchmark_runs/run_{timestamp_str}")

    selected_providers = _parse_providers(args.providers)

    print_banner(
        title="Multi-Provider RAG Benchmark & Leaderboard",
        subtitle=f"Benchmarking Providers: {', '.join(p.upper() for p in selected_providers)}",
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
        print_error("Dataset contains 0 benchmark samples.")
        return 1

    config = EvaluationConfiguration(
        k_values=[1, 3, 5, 10],
        max_concurrency=args.concurrency,
        timeout_seconds=args.timeout,
        providers=selected_providers,
        prompt_strategy=args.strategy,
        dataset_name=str(args.dataset or "builtin_benchmark"),
    )

    print_key_values(
        {
            "Dataset Source": str(args.dataset or "Builtin Benchmark Suite"),
            "Sample Count": len(samples),
            "Providers": ", ".join(selected_providers),
            "Prompt Strategy": args.strategy,
            "Concurrency per Provider": args.concurrency,
            "Output Directory": str(out_dir_path),
        },
        title="Benchmark Execution Parameters",
    )

    _cancel_event = setup_signal_handling()

    # 2. Instantiate Benchmark Engine through DI
    benchmark_engine = create_cli_benchmark(providers=selected_providers)

    start_time = time.perf_counter()
    result: BenchmarkResult | None = None

    total_evaluations = len(selected_providers) * len(samples)
    with create_progress() as progress:
        task_id = progress.add_task(
            f"[cyan]Benchmarking {len(selected_providers)} provider(s) across {len(samples)} samples...",
            total=total_evaluations,
        )

        try:
            result = await benchmark_engine.run(samples=samples, config=config)
            progress.update(task_id, completed=total_evaluations)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print_warning("\nBenchmark interrupted by user.")
            return 130
        except Exception as exc:  # noqa: BLE001
            print_error(f"Benchmark run failed: {exc}", exc=exc)
            return 1

    elapsed_time = time.perf_counter() - start_time

    # 3. Export Artifacts
    artifacts = EvaluationExporter.export_benchmark(result, out_dir_path)

    # 4. Build Analytics DataFrames (validating analytics layer)
    try:
        _ = ProviderComparisonFrame.benchmark_to_dataframe(result)
        _ = LeaderboardFrame.to_dataframe(result)
    except Exception as exc:  # noqa: BLE001
        logger.warning("benchmark_dataframe_warning", error=str(exc))

    # 5. Render Rich Leaderboard Table
    print_section("Leaderboard Rankings")
    table = Table(
        title=f"Provider Leaderboard ({len(samples)} samples / provider)",
        border_style="bright_blue",
        header_style="bold cyan",
    )
    table.add_column("Rank", justify="center", style="bold")
    table.add_column("Provider", style="bold white")
    table.add_column("Model", style="dim")
    table.add_column("Score", justify="right", style="bold bright_green")
    table.add_column("Faithfulness", justify="right", style="cyan")
    table.add_column("Hallucination", justify="right", style="yellow")
    table.add_column("Citations", justify="right", style="cyan")
    table.add_column("Recall@5", justify="right", style="white")
    table.add_column("Avg Latency", justify="right", style="dim")
    table.add_column("Success", justify="right", style="green")

    for entry in result.leaderboard:
        rank_badge = f"[bold yellow]#{entry.get('rank', 1)}[/bold yellow]"
        prov_badge = f"[bold cyan]{entry.get('provider', '').upper()}[/bold cyan]"
        success_count = entry.get("successful_samples", 0)
        total_count = entry.get("total_samples", 1)
        succ_pct = (success_count / max(1, total_count)) * 100.0

        table.add_row(
            rank_badge,
            prov_badge,
            entry.get("model") or "default",
            f"{entry.get('composite_score', 0.0):.4f}",
            format_pct(entry.get("avg_faithfulness", 0.0)),
            format_pct(entry.get("avg_hallucination_rate", 0.0)),
            format_pct(entry.get("avg_citation_coverage", 0.0)),
            format_pct(entry.get("avg_recall_at_5", 0.0)),
            format_ms(entry.get("avg_latency_ms", 0.0)),
            f"{succ_pct:.0f}%",
        )

    console.print(table)

    # 6. Winning Provider Banner
    if result.leaderboard:
        winner = result.leaderboard[0]
        winner_name = winner.get("provider", "N/A").upper()
        winner_score = winner.get("composite_score", 0.0)
        console.print(
            Panel(
                f"[bold bright_green]Top Performing Provider: {winner_name}[/bold bright_green] "
                f"(Composite Score: [bold cyan]{winner_score:.4f}[/bold cyan])",
                border_style="bright_green",
                padding=(1, 2),
            )
        )

    # 7. Artifacts Summary
    print_section("Generated Artifacts")
    print_key_values(
        {k: str(v) for k, v in artifacts.items()},
        title="Saved Benchmark Reports",
    )

    print_success(f"Benchmark completed successfully in {format_duration(elapsed_time)}.")
    return 0


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.verbose:
        os.environ["INVESTIGA_VERBOSE"] = "1"

    try:
        exit_code = asyncio.run(run_benchmark(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        get_console().print("\n[warning]Operation interrupted.[/warning]")
        sys.exit(130)


if __name__ == "__main__":
    main()
