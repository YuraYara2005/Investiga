#!/usr/bin/env python3
"""Investiga System Verification & Telemetry Inspector.

Probes and reports live operational status of PostgreSQL, Qdrant vector store,
relational document/chunk metadata, and embedding services with rich terminal visualization.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
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

from rich.table import Table
from sqlalchemy import func, select

from app.auth.models.permission import Permission
from app.auth.models.role import Role
from app.auth.models.user import User
from app.core.config import get_settings
from app.core.logging import get_logger
from app.knowledge.models.knowledge_chunk import KnowledgeChunk
from app.knowledge.models.knowledge_document import KnowledgeDocument
from scripts.common.console import (
    get_console,
    print_banner,
    print_error,
    print_key_values,
    print_section,
    print_success,
    print_warning,
)
from scripts.common.factory import (
    create_cli_embedding_service,
    create_cli_vector_repository,
    get_cli_db_session,
)
from scripts.common.helpers import format_bytes, format_duration, format_ms

logger = get_logger(__name__)


async def verify_postgres() -> dict[str, int | str]:
    """Inspect PostgreSQL relational tables and record counts."""
    console = get_console()
    results: dict[str, int | str] = {}

    try:
        async with get_cli_db_session() as session:
            # Check users
            users_cnt = (await session.execute(select(func.count(User.id)))).scalar_one() or 0
            # Check roles
            roles_cnt = (await session.execute(select(func.count(Role.id)))).scalar_one() or 0
            # Check permissions
            perms_cnt = (await session.execute(select(func.count(Permission.id)))).scalar_one() or 0
            # Check documents
            docs_cnt = (await session.execute(select(func.count(KnowledgeDocument.id)))).scalar_one() or 0
            # Check chunks
            chunks_cnt = (await session.execute(select(func.count(KnowledgeChunk.id)))).scalar_one() or 0

            results["status"] = "CONNECTED"
            results["users"] = users_cnt
            results["roles"] = roles_cnt
            results["permissions"] = perms_cnt
            results["documents"] = docs_cnt
            results["chunks"] = chunks_cnt

            # Query recent documents
            recent_docs = (
                (
                    await session.execute(
                        select(KnowledgeDocument)
                        .order_by(KnowledgeDocument.created_at.desc())
                        .limit(5)
                    )
                )
                .scalars()
                .all()
            )

            if recent_docs:
                print_section("Recent PostgreSQL Documents (Top 5)")
                doc_table = Table(
                    title="Indexed Relational Documents",
                    border_style="bright_blue",
                    header_style="bold cyan",
                )
                doc_table.add_column("Title", style="bold white")
                doc_table.add_column("Category", style="cyan")
                doc_table.add_column("Size", justify="right", style="green")
                doc_table.add_column("Checksum (SHA-256)", style="dim white")
                doc_table.add_column("Chunks", justify="right", style="yellow")
                doc_table.add_column("Status", style="bold")

                for d in recent_docs:
                    c_count = len(d.chunks) if d.chunks else 0
                    cat_val = d.category.value if hasattr(d.category, "value") else str(d.category)
                    status_val = d.processing_status.value if hasattr(d.processing_status, "value") else str(d.processing_status)
                    doc_table.add_row(
                        d.title[:35],
                        cat_val,
                        format_bytes(d.file_size),
                        f"{d.checksum[:8]}...{d.checksum[-6:]}",
                        str(c_count),
                        f"[green]{status_val}[/green]" if status_val == "READY" else f"[yellow]{status_val}[/yellow]",
                    )
                console.print(doc_table)

    except Exception as exc:
        results["status"] = f"FAILED: {exc}"
        print_error(f"PostgreSQL probe failed: {exc}")

    return results


async def verify_qdrant() -> dict[str, int | str]:
    """Inspect Qdrant collection and vector points."""
    console = get_console()
    results: dict[str, int | str] = {}
    settings = get_settings()

    try:
        vec_repo = create_cli_vector_repository(settings=settings)
        provider = vec_repo._provider
        collection_name = settings.vectorstore.collection_name
        exists = await provider.collection_exists(collection_name=collection_name)

        if not exists:
            results["status"] = "COLLECTION_NOT_FOUND"
            results["collection_name"] = collection_name
            results["vectors_count"] = 0
            return results

        stats = await provider.get_collection_stats(collection_name=collection_name)
        results["status"] = "READY"
        results["collection_name"] = stats.collection_name
        results["vectors_count"] = stats.vectors_count
        results["points_count"] = stats.points_count
        results["vector_size"] = stats.vector_size
        results["distance"] = stats.distance

        print_section("Qdrant Vector Database Telemetry")
        print_key_values(
            {
                "Status": f"[bold green]{results['status']}[/bold green]",
                "Collection": str(results["collection_name"]),
                "Stored Vectors": str(results["vectors_count"]),
                "Stored Points": str(results["points_count"]),
                "Vector Dimension": str(results["vector_size"]),
                "Distance Metric": str(results["distance"]),
                "Host / Endpoint": f"{settings.vectorstore.host}:{settings.vectorstore.port}",
            },
            title="Qdrant Vector Store",
        )

    except Exception as exc:
        results["status"] = f"FAILED: {exc}"
        print_error(f"Qdrant probe failed: {exc}")

    return results


async def verify_embeddings() -> dict[str, str | int]:
    """Inspect embedding engine."""
    results: dict[str, str | int] = {}
    settings = get_settings()

    try:
        emb_service = create_cli_embedding_service(settings=settings, auto_load=True)
        info = emb_service.model_info
        results["model_name"] = info.model_name
        results["provider"] = info.provider
        results["dimension"] = info.dimension
        results["device"] = info.device

        # Run sample encoding
        t0 = time.perf_counter()
        sample_res = emb_service.embed_text("Investiga incident response runbook check.")
        lat_ms = (time.perf_counter() - t0) * 1000

        results["test_encoding_latency"] = format_ms(lat_ms)
        results["test_vector_length"] = len(sample_res.vector)
        results["status"] = "OPERATIONAL"

    except Exception as exc:
        results["status"] = f"FAILED: {exc}"
        print_error(f"Embedding service probe failed: {exc}")

    return results


async def main_async() -> int:
    """Run full system verification."""
    console = get_console()
    print_banner(
        title="Investiga System Verification & Telemetry",
        subtitle="PostgreSQL, Qdrant Vector Store & Embedding Engine Diagnostics",
    )

    t_start = time.perf_counter()

    # 1. PostgreSQL
    print_section("1. Relational Database (PostgreSQL)")
    pg_res = await verify_postgres()

    # 2. Qdrant
    print_section("2. Vector Database (Qdrant)")
    qd_res = await verify_qdrant()

    # 3. Embeddings
    print_section("3. Embedding Pipeline")
    emb_res = await verify_embeddings()

    # 4. Summary Table
    print_section("System Verification Overview")
    summary_table = Table(
        title="Subsystem Health & Operational Readiness",
        border_style="bright_blue",
        header_style="bold cyan",
    )
    summary_table.add_column("Subsystem", style="bold white")
    summary_table.add_column("Status", style="bold")
    summary_table.add_column("Key Telemetry / Metrics", style="dim cyan")

    # PG Row
    pg_ok = pg_res.get("status") == "CONNECTED"
    summary_table.add_row(
        "PostgreSQL Relational DB",
        "[bold green]HEALTHY[/bold green]" if pg_ok else f"[bold red]{pg_res.get('status')}[/bold red]",
        f"Docs: {pg_res.get('documents', 0)} | Chunks: {pg_res.get('chunks', 0)} | Users: {pg_res.get('users', 0)}",
    )

    # Qdrant Row
    qd_ok = qd_res.get("status") == "READY"
    summary_table.add_row(
        "Qdrant Vector Database",
        "[bold green]HEALTHY[/bold green]" if qd_ok else f"[bold yellow]{qd_res.get('status')}[/bold yellow]",
        f"Collection: {qd_res.get('collection_name', 'N/A')} | Vectors: {qd_res.get('vectors_count', 0)} ({qd_res.get('vector_size', 'N/A')}d)",
    )

    # Embedding Row
    emb_ok = emb_res.get("status") == "OPERATIONAL"
    summary_table.add_row(
        "Embedding Pipeline",
        "[bold green]HEALTHY[/bold green]" if emb_ok else f"[bold red]{emb_res.get('status')}[/bold red]",
        f"Model: {emb_res.get('model_name')} ({emb_res.get('dimension')}d) | Latency: {emb_res.get('test_encoding_latency')}",
    )

    console.print(summary_table)

    total_time = time.perf_counter() - t_start
    print_success(f"System verification complete in {format_duration(total_time)}.")
    return 0 if (pg_ok and qd_ok and emb_ok) else 1


def main() -> None:
    exit_code = asyncio.run(main_async())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
