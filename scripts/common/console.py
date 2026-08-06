"""Rich Console and UI Utilities for Investiga CLI.

Provides unified styling, themed headers, progress bars, tables, panels,
and signal handling for graceful cancellation.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from collections.abc import Callable
from typing import Any

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

# Custom brand theme for Investiga
INVESTIGA_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "primary": "bold bright_blue",
    "secondary": "bright_cyan",
    "muted": "dim white",
    "accent": "bold magenta",
    "metric.label": "bold white",
    "metric.value": "bold bright_cyan",
})

# Singleton console with safe rendering
_console = Console(theme=INVESTIGA_THEME, safe_box=True)


def get_console() -> Console:
    """Retrieve shared Rich Console instance."""
    return _console


def print_banner(
    title: str,
    subtitle: str | None = None,
    tagline: str = "Investiga Enterprise Incident Investigation Platform",
) -> None:
    """Render branded top-level header banner."""
    console = get_console()

    header_text = Text()
    header_text.append("[INVESTIGA] ", style="bold bright_cyan")
    header_text.append(tagline.upper(), style="bold bright_blue")
    header_text.append("\n\n", style="default")
    header_text.append(title, style="bold white")

    if subtitle:
        header_text.append(f"\n{subtitle}", style="dim white")

    panel = Panel(
        Align.center(header_text),
        border_style="bright_blue",
        padding=(1, 2),
        expand=False,
    )
    console.print()
    console.print(panel)
    console.print()


def print_section(title: str) -> None:
    """Print section divider."""
    console = get_console()
    console.print(f"\n[bold bright_blue]--- {title} [/][dim bright_blue]{'-' * max(5, 50 - len(title))}[/]")


def print_info(message: str) -> None:
    """Print informational notice."""
    get_console().print(f"[info][i][/info] {message}")


def print_success(message: str) -> None:
    """Print success message."""
    get_console().print(f"[success][v][/success] {message}")


def print_warning(message: str) -> None:
    """Print warning notice."""
    get_console().print(f"[warning][!][/warning] {message}")


def print_error(message: str, exc: Exception | None = None) -> None:
    """Print error notice with optional exception detail."""
    console = get_console()
    console.print(f"[error][x] {message}[/error]")
    if exc is not None and os.getenv("INVESTIGA_VERBOSE", "").lower() in ("1", "true"):
        console.print_exception(show_locals=False)


def print_key_values(
    data: dict[str, Any],
    title: str | None = None,
    border_style: str = "bright_blue",
) -> None:
    """Print key-value summary table."""
    table = Table(
        title=title,
        show_header=False,
        border_style=border_style,
        box=None,
        padding=(0, 2),
    )
    table.add_column("Key", style="bold cyan")
    table.add_column("Value", style="bold white")

    for k, v in data.items():
        table.add_row(str(k), str(v))

    get_console().print(table)


def create_progress() -> Progress:
    """Construct Rich progress bar with throughput and timer columns."""
    return Progress(
        SpinnerColumn(spinner_name="dots", style="bright_cyan"),
        TextColumn("[bold bright_blue]{task.description}[/]"),
        BarColumn(
            bar_width=40,
            style="dim bright_blue",
            complete_style="bright_cyan",
            finished_style="bold green",
        ),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=get_console(),
        transient=False,
    )


class GracefulExit(SystemExit):
    """Exception raised on graceful cancellation (Ctrl+C)."""


def setup_signal_handling(
    cancellation_callback: Callable[[], None] | None = None,
) -> asyncio.Event:
    """Configure Ctrl+C (SIGINT) interception with an asyncio.Event flag.

    Args:
        cancellation_callback: Optional sync/async cleanup hook.

    Returns:
        asyncio.Event: Set when SIGINT / SIGTERM is intercepted.
    """
    cancel_event = asyncio.Event()
    loop = asyncio.get_event_loop()

    def _on_signal() -> None:
        if cancel_event.is_set():
            # Second Ctrl+C forces immediate termination
            get_console().print("\n[error]Force stopping...[/error]")
            sys.exit(130)

        cancel_event.set()
        get_console().print("\n[warning]Interruption detected (Ctrl+C). Gracefully cancelling... (Press again to force exit)[/warning]")
        if cancellation_callback:
            try:
                cancellation_callback()
            except (RuntimeError, ValueError, OSError):
                pass

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _on_signal)
            except (NotImplementedError, RuntimeError):
                signal.signal(sig, lambda _s, _f: _on_signal())
    else:
        # Windows signal handling
        signal.signal(signal.SIGINT, lambda _s, _f: _on_signal())

    return cancel_event
