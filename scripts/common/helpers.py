"""Helper utilities for Investiga Operational CLI.

Provides environment bootstrapping, path resolution, and value formatting.
"""

from __future__ import annotations

import sys
from pathlib import Path


def bootstrap_environment() -> None:
    """Ensure backend is in sys.path and load environment variables."""
    # Ensure UTF-8 output on Windows consoles
    if sys.platform == "win32":
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass

    # Find backend directory relative to this script
    script_dir = Path(__file__).resolve().parent.parent  # /scripts
    repo_root = script_dir.parent                        # /d:/Investiga
    backend_dir = repo_root / "backend"                  # /d:/Investiga/backend

    # 1. Add backend to sys.path if not present
    backend_str = str(backend_dir)
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)

    repo_str = str(repo_root)
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)

    # 2. Try loading .env or .env.development if dotenv is installed
    try:
        from dotenv import load_dotenv

        env_dev = backend_dir / ".env.development"
        env_main = backend_dir / ".env"
        env_root = repo_root / ".env"

        if env_dev.exists():
            load_dotenv(env_dev)
        elif env_main.exists():
            load_dotenv(env_main)
        elif env_root.exists():
            load_dotenv(env_root)
    except ImportError:
        pass


def resolve_path(path_str: str | Path, base_dir: Path | None = None) -> Path:
    """Resolve a path relative to working directory or optional base."""
    p = Path(path_str)
    if p.is_absolute():
        return p.resolve()
    base = base_dir or Path.cwd()
    return (base / p).resolve()


def format_bytes(size: float | None) -> str:
    """Format byte count into human-readable representation."""
    if size is None:
        return "0 B"
    size_float = float(size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size_float) < 1024.0:
            return f"{size_float:.1f} {unit}" if unit != "B" else f"{int(size_float)} B"
        size_float /= 1024.0
    return f"{size_float:.1f} PB"


def format_duration(seconds: float | None) -> str:
    """Format seconds into readable duration string."""
    if seconds is None or seconds < 0:
        return "0.00s"
    if seconds < 1.0:
        return f"{seconds * 1000.0:.0f}ms"
    if seconds < 60.0:
        return f"{seconds:.2f}s"
    minutes = int(seconds // 60)
    rem_seconds = seconds % 60
    if minutes < 60:
        return f"{minutes}m {rem_seconds:.1f}s"
    hours = int(minutes // 60)
    rem_minutes = minutes % 60
    return f"{hours}h {rem_minutes}m"


def format_ms(ms: float | None) -> str:
    """Format millisecond latency with proper precision."""
    if ms is None:
        return "N/A"
    if ms < 1000.0:
        return f"{ms:.1f}ms"
    return f"{ms / 1000.0:.2f}s"


def format_score(score: float | None, precision: int = 4) -> str:
    """Format metric score to fixed precision percentage or float."""
    if score is None:
        return "N/A"
    return f"{score:.{precision}f}"


def format_pct(score: float | None) -> str:
    """Format metric score as a percentage."""
    if score is None:
        return "N/A"
    return f"{score * 100.0:.1f}%"
