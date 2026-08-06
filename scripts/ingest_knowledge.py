#!/usr/bin/env python3
"""Investiga Knowledge Ingestion CLI.

Executes the complete ETL -> Ingestion -> Chunking -> Embedding -> Qdrant pipeline
with recursive directory traversal, Rich progress telemetry, duplicate skipping,
dry-run preview, and graceful cancellation.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
import uuid
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
from app.etl.exceptions import ETLJobCancelledException
# pyrefly: ignore [missing-import]
from app.etl.loaders.filesystem_loader import FilesystemLoader
# pyrefly: ignore [missing-import]
from app.etl.models import (
    ETLConfiguration,
    ETLJob,
    ETLJobStatus,
    ETLResult,
    ETLSource,
)
from rich.table import Table

from scripts.common.console import (
    create_progress,
    get_console,
    print_banner,
    print_error,
    print_key_values,
    print_section,
    print_success,
    print_warning,
    setup_signal_handling,
)
from scripts.common.factory import (
    create_cli_etl_service,
    get_cli_db_session,
)
from scripts.common.helpers import (
    format_bytes,
    format_duration,
    resolve_path,
)

logger = get_logger(__name__)

# Default system UUID for CLI operations
DEFAULT_SYSTEM_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser for knowledge ingestion."""
    parser = argparse.ArgumentParser(
        prog="investiga-ingest",
        description="Ingest directories and documents into the Investiga Enterprise Knowledge Base.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Core source options
    parser.add_argument(
        "--source",
        "-s",
        type=str,
        required=True,
        help="Path to directory containing documents to ingest.",
    )
    parser.add_argument(
        "--recursive",
        "-r",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Recursively scan subdirectories for documents.",
    )
    parser.add_argument(
        "--category",
        "-c",
        type=str,
        default=None,
        help="Knowledge domain category (e.g., Engineering, Legal, Incidents).",
    )

    # Filters
    parser.add_argument(
        "--include-ext",
        "--allowed-extensions",
        type=str,
        default=None,
        help="Comma-separated allowed extensions (e.g., .py,.md,.txt,.pdf,.html,.json).",
    )
    parser.add_argument(
        "--exclude-ext",
        type=str,
        default=None,
        help="Comma-separated excluded extensions.",
    )
    parser.add_argument(
        "--include-patterns",
        type=str,
        default=None,
        help="Comma-separated glob include patterns (e.g., *).",
    )
    parser.add_argument(
        "--exclude-patterns",
        type=str,
        default=None,
        help="Comma-separated glob exclude patterns (e.g., *.tmp,node_modules/*,.git/*).",
    )

    # Performance and batching
    parser.add_argument(
        "--batch-size",
        "-b",
        type=int,
        default=10,
        help="Number of documents to process and vectorize per batch.",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=None,
        help="Number of concurrent worker tasks (mapped to processing concurrency).",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Maximum number of files to discover and process.",
    )

    # Chunking overrides
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="Override semantic chunk size (tokens).",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=None,
        help="Override semantic chunk overlap (tokens).",
    )

    # Execution modes
    parser.add_argument(
        "--force-reindex",
        action="store_true",
        default=False,
        help="Force re-indexing and overwrite existing embeddings for duplicates.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Discover and display candidate files without parsing or storing vectors.",
    )
    parser.add_argument(
        "--resume-job-id",
        type=str,
        default=None,
        help="UUID of an interrupted ETL job to resume from its checkpoint cursor.",
    )
    parser.add_argument(
        "--user-id",
        "-u",
        type=str,
        default=None,
        help="UUID of the user performing ingestion (defaults to system UUID).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Enable verbose debug output.",
    )

    return parser


def _parse_csv_list(val: str | None) -> list[str] | None:
    """Parse comma-separated string into list of trimmed strings."""
    if not val:
        return None
    return [item.strip() for item in val.split(",") if item.strip()]


async def run_dry_run(
    source_path: Path,
    config: ETLConfiguration,
) -> int:
    """Execute dry-run discovery and render candidate files table."""
    console = get_console()
    print_banner(
        title="Knowledge Ingestion (DRY RUN)",
        subtitle=f"Scanning {source_path}",
    )

    loader = FilesystemLoader()
    discovered_items = []
    total_size = 0

    with create_progress() as progress:
        task_id = progress.add_task("[cyan]Discovering candidate documents...", total=None)
        async for item in loader.discover(config):
            discovered_items.append(item)
            total_size += item.size_bytes
            progress.update(task_id, advance=1)

    print_section("Discovered Documents Preview")
    table = Table(
        title=f"Discovered {len(discovered_items)} candidate file(s) ({format_bytes(total_size)})",
        border_style="bright_blue",
        header_style="bold cyan",
    )
    table.add_column("#", style="dim", justify="right")
    table.add_column("Filename", style="bold white")
    table.add_column("Relative Path", style="dim cyan")
    table.add_column("Ext", style="yellow")
    table.add_column("Size", justify="right", style="green")
    table.add_column("MIME Type", style="dim white")

    for idx, it in enumerate(discovered_items[:50], 1):
        table.add_row(
            str(idx),
            it.filename,
            it.relative_path,
            it.extension,
            format_bytes(it.size_bytes),
            it.mime_type or "N/A",
        )

    console.print(table)
    if len(discovered_items) > 50:
        console.print(f"[dim](... and {len(discovered_items) - 50} more files)[/dim]")

    print_key_values(
        {
            "Total Documents": len(discovered_items),
            "Total Size": format_bytes(total_size),
            "Source Directory": str(source_path),
            "Recursive": config.recursive,
            "Allowed Extensions": ", ".join(config.allowed_extensions) if config.allowed_extensions else "All supported",
            "Category": config.category or "Default",
        },
        title="Dry Run Summary",
    )

    print_success("Dry run completed successfully. No changes were made to the database or vector store.")
    return 0


async def run_ingestion(args: argparse.Namespace) -> int:
    """Execute complete ETL -> Ingestion pipeline."""
    console = get_console()
    source_path = resolve_path(args.source)

    if not source_path.exists():
        print_error(f"Source directory does not exist: {source_path}")
        return 1

    if not source_path.is_dir():
        print_error(f"Source path is not a directory: {source_path}")
        return 1

    # User ID parsing
    user_id = DEFAULT_SYSTEM_USER_ID
    if args.user_id:
        try:
            user_id = uuid.UUID(args.user_id)
        except ValueError:
            print_error(f"Invalid user UUID: {args.user_id}")
            return 1

    # Extensions and patterns
    allowed_exts = _parse_csv_list(args.include_ext)
    excluded_exts = _parse_csv_list(args.exclude_ext)
    include_patterns = _parse_csv_list(args.include_patterns) or ["*"]
    exclude_patterns = _parse_csv_list(args.exclude_patterns) or []

    if excluded_exts:
        for ext in excluded_exts:
            pattern = f"*{ext}" if ext.startswith(".") else f"*.{ext}"
            if pattern not in exclude_patterns:
                exclude_patterns.append(pattern)

    batch_size = args.workers or args.batch_size or 10

    config = ETLConfiguration(
        source_type=ETLSource.FILESYSTEM,
        source_path_or_uri=str(source_path),
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        allowed_extensions=allowed_exts,
        recursive=args.recursive,
        batch_size=batch_size,
        max_files=args.max_files,
        force_reindex=args.force_reindex,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        category=args.category,
    )

    if args.dry_run:
        return await run_dry_run(source_path, config)

    print_banner(
        title="Knowledge Ingestion Pipeline",
        subtitle=f"Source: {source_path}",
    )

    print_key_values(
        {
            "Source Path": str(source_path),
            "Category": args.category or "General",
            "Recursive": args.recursive,
            "Batch Size": batch_size,
            "Force Reindex": args.force_reindex,
            "Allowed Extensions": ", ".join(allowed_exts) if allowed_exts else "All supported",
        },
        title="Configuration",
    )

    cancel_event = setup_signal_handling()
    etl_service = create_cli_etl_service()

    start_time = time.perf_counter()
    result: ETLResult | None = None

    try:
        with create_progress() as progress:
            task_id = progress.add_task("[cyan]Ingesting & Vectorizing documents...", total=None)

            async with get_cli_db_session() as session:
                # Step 1: Discover documents
                loader = FilesystemLoader()
                discovered = []
                async for item in loader.discover(config):
                    if cancel_event.is_set():
                        raise ETLJobCancelledException()
                    discovered.append(item)

                progress.update(task_id, total=len(discovered))

                # Step 2: Create ETL Job
                job = ETLJob(
                    job_id=uuid.UUID(args.resume_job_id) if args.resume_job_id else uuid.uuid4(),
                    user_id=user_id,
                    source_type=ETLSource.FILESYSTEM,
                    config=config,
                    discovered_items=discovered,
                )

                # Step 3: Run pipeline with cancellation support
                result = await etl_service.pipeline.execute(
                    job=job,
                    session=session,
                    cancellation_token=cancel_event,
                )
                progress.update(task_id, completed=len(discovered))

    except (ETLJobCancelledException, asyncio.CancelledError):
        print_warning("\nIngestion cancelled by user. Checkpoints preserved where applicable.")
        return 130
    except Exception as exc:  # noqa: BLE001
        print_error(f"Ingestion failed: {exc}", exc=exc)
        return 1

    elapsed_time = time.perf_counter() - start_time

    # Render Summary Table
    print_section("Ingestion Summary")

    summary_table = Table(
        title="Knowledge Ingestion Telemetry & Execution Summary",
        border_style="bright_blue",
        header_style="bold cyan",
    )
    summary_table.add_column("Metric", style="bold white")
    summary_table.add_column("Value", style="bold bright_cyan")

    stats = result.stats
    summary_table.add_row("Status", f"[bold green]{result.status.value.upper()}[/bold green]" if result.status == ETLJobStatus.COMPLETED else f"[bold yellow]{result.status.value.upper()}[/bold yellow]")
    summary_table.add_row("Documents Discovered", str(stats.files_discovered))
    summary_table.add_row("Documents Processed / Indexed", str(stats.files_processed))
    summary_table.add_row("Documents Skipped (Duplicates)", str(stats.files_skipped))
    summary_table.add_row("Documents Failed", f"[red]{stats.files_failed}[/red]" if stats.files_failed > 0 else "0")
    summary_table.add_row("Chunks Created", str(stats.total_chunks))
    summary_table.add_row("Vectors Stored (Qdrant)", str(stats.total_vectors))
    summary_table.add_row("Elapsed Time", format_duration(elapsed_time))
    chunks_per_sec = stats.total_chunks / max(0.001, stats.elapsed_time_seconds)
    summary_table.add_row("Throughput", f"{stats.throughput_files_per_second:.2f} docs/sec | {chunks_per_sec:.2f} chunks/sec")

    console.print(summary_table)

    if result.errors:
        print_section("Encountered Errors")
        for err in result.errors[:10]:
            print_error(err)
        if len(result.errors) > 10:
            console.print(f"[dim](and {len(result.errors) - 10} more errors)[/dim]")

    if result.status == ETLJobStatus.COMPLETED:
        print_success(f"Ingestion finished successfully in {format_duration(elapsed_time)}.")
        return 0
    else:
        print_warning("Ingestion finished with partial errors.")
        return 1


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.verbose:
        os.environ["INVESTIGA_VERBOSE"] = "1"

    try:
        exit_code = asyncio.run(run_ingestion(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        get_console().print("\n[warning]Operation interrupted.[/warning]")
        sys.exit(130)


if __name__ == "__main__":
    main()
