#!/usr/bin/env python3
"""Investiga Interactive Enterprise RAG Assistant CLI.

Provides a terminal REPL for natural-language inquiry over ingested knowledge,
supporting dynamic provider switching (Gemini, Ollama, Mock), prompt strategy selection,
rich markdown rendering, citation inspection, context visualization, and latency telemetry.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
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
from app.rag.models import (
    LLMMessage,
    MessageRole,
    RAGRequest,
    RAGResponse,
)
# pyrefly: ignore [missing-import]
from app.rag.service import RAGService
# pyrefly: ignore [missing-import]
from app.retrieval.models import SearchFilters, SearchOptions
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from scripts.common.console import (
    get_console,
    print_banner,
    print_error,
    print_info,
    print_key_values,
    print_success,
    print_warning,
)
from scripts.common.factory import (
    build_cli_bm25_index_async,
    create_cli_rag_service,
    create_cli_retrieval_service,
)
from scripts.common.helpers import (
    format_ms,
)

logger = get_logger(__name__)

SUPPORTED_PROVIDERS = ["gemini", "ollama", "mock"]
SUPPORTED_STRATEGIES = [
    "standard_qa",
    "investigative_analysis",
    "executive_summary",
    "extractive",
    "concise",
]


def build_parser() -> argparse.ArgumentParser:
    """Construct argument parser for interactive chat session."""
    parser = argparse.ArgumentParser(
        prog="investiga-chat",
        description="Interactive Enterprise RAG Assistant CLI for Investiga.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--provider",
        "-p",
        type=str,
        default="mock",
        choices=SUPPORTED_PROVIDERS,
        help="Initial LLM provider to use for generation.",
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="Model name override (e.g. 'gemini-1.5-pro', 'llama3:8b').",
    )
    parser.add_argument(
        "--strategy",
        "-s",
        type=str,
        default="standard_qa",
        choices=SUPPORTED_STRATEGIES,
        help="Initial prompt synthesis strategy.",
    )
    parser.add_argument(
        "--category",
        "-c",
        type=str,
        default=None,
        help="Filter retrieval to a specific document category.",
    )
    parser.add_argument(
        "--top-k",
        "-k",
        type=int,
        default=5,
        help="Number of top relevant chunks to retrieve.",
    )
    parser.add_argument(
        "--stream",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Stream response tokens in real-time.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Enable verbose telemetry output.",
    )
    return parser


class ChatSession:
    """Manages the interactive chat lifecycle, state, and commands."""

    def __init__(
        self,
        rag_service: RAGService,
        provider: str = "mock",
        model: str | None = None,
        strategy: str = "standard_qa",
        category: str | None = None,
        top_k: int = 5,
        stream: bool = False,
    ) -> None:
        self.rag_service = rag_service
        self.provider = provider
        self.model = model
        self.strategy = strategy
        self.category = category
        self.top_k = top_k
        self.stream = stream

        self.history: list[LLMMessage] = []
        self.show_context = False
        self.show_citations = True
        self.show_metrics = True

    def display_help(self) -> None:
        """Render available commands and current configuration table."""
        console = get_console()
        table = Table(
            title="Investiga Interactive Assistant - Commands & Shortcuts",
            border_style="bright_blue",
            header_style="bold cyan",
        )
        table.add_column("Command", style="bold white")
        table.add_column("Description", style="dim white")
        table.add_column("Current Value", style="bold bright_cyan")

        table.add_row("exit, quit, q", "Terminate the interactive session", "")
        table.add_row("clear, cls", "Clear the terminal screen", "")
        table.add_row("/history", "Display conversation turn history", f"{len(self.history)} messages")
        table.add_row(f"/provider <{','.join(SUPPORTED_PROVIDERS)}>", "Switch active LLM provider", self.provider)
        table.add_row("/strategy <name>", "Switch prompt strategy", self.strategy)
        table.add_row("/show-context, /context", "Toggle display of retrieved context chunks", "ON" if self.show_context else "OFF")
        table.add_row("/show-citations, /citations", "Toggle detailed citations panel", "ON" if self.show_citations else "OFF")
        table.add_row("/show-metrics, /metrics", "Toggle latency & token telemetry", "ON" if self.show_metrics else "OFF")
        table.add_row("/help, /?", "Show this help table", "")

        console.print(table)

    def display_history(self) -> None:
        """Render full conversation history."""
        console = get_console()
        if not self.history:
            print_info("Conversation history is currently empty.")
            return

        table = Table(
            title="Conversation History",
            border_style="bright_blue",
            header_style="bold cyan",
        )
        table.add_column("#", style="dim", justify="right")
        table.add_column("Role", style="bold")
        table.add_column("Content Snippet", style="white")

        for idx, msg in enumerate(self.history, 1):
            role_style = "bright_blue" if msg.role == MessageRole.USER else "bright_green"
            role_str = f"[{role_style}]{msg.role.value.upper()}[/{role_style}]"
            snippet = msg.content[:120] + "..." if len(msg.content) > 120 else msg.content
            table.add_row(str(idx), role_str, snippet)

        console.print(table)

    def handle_command(self, cmd_str: str) -> bool:
        """Handle slash command or terminal control string. Returns True to continue."""
        console = get_console()
        parts = cmd_str.strip().split()
        if not parts:
            return True

        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("exit", "quit", "q"):
            print_info("Ending session. Goodbye!")
            return False

        elif cmd in ("clear", "cls"):
            console.clear()
            self.display_welcome()
            return True

        elif cmd == "/history":
            self.display_history()
            return True

        elif cmd == "/provider":
            if not args:
                print_warning(f"Usage: /provider <{','.join(SUPPORTED_PROVIDERS)}> [model_name]")
            else:
                new_prov = args[0].lower()
                if new_prov in SUPPORTED_PROVIDERS:
                    self.provider = new_prov
                    if len(args) > 1:
                        self.model = args[1]
                    else:
                        self.model = None
                    print_success(f"Switched LLM provider to [bold cyan]{self.provider}[/bold cyan]" + (f" (model: {self.model})" if self.model else ""))
                else:
                    print_error(f"Unknown provider '{new_prov}'. Supported: {', '.join(SUPPORTED_PROVIDERS)}")
            return True

        elif cmd == "/strategy":
            if not args:
                print_warning(f"Usage: /strategy <{','.join(SUPPORTED_STRATEGIES)}>")
            else:
                new_strat = args[0].lower()
                if new_strat in SUPPORTED_STRATEGIES:
                    self.strategy = new_strat
                    print_success(f"Switched prompt strategy to [bold cyan]{self.strategy}[/bold cyan]")
                else:
                    print_error(f"Unknown strategy '{new_strat}'. Supported: {', '.join(SUPPORTED_STRATEGIES)}")
            return True

        elif cmd in ("/show-context", "/context"):
            self.show_context = not self.show_context
            state_str = "[bold green]ON[/bold green]" if self.show_context else "[bold yellow]OFF[/bold yellow]"
            print_info(f"Retrieved context display is now {state_str}")
            return True

        elif cmd in ("/show-citations", "/citations"):
            self.show_citations = not self.show_citations
            state_str = "[bold green]ON[/bold green]" if self.show_citations else "[bold yellow]OFF[/bold yellow]"
            print_info(f"Citations display is now {state_str}")
            return True

        elif cmd in ("/show-metrics", "/metrics"):
            self.show_metrics = not self.show_metrics
            state_str = "[bold green]ON[/bold green]" if self.show_metrics else "[bold yellow]OFF[/bold yellow]"
            print_info(f"Metrics display is now {state_str}")
            return True

        elif cmd in ("/help", "/?"):
            self.display_help()
            return True

        else:
            print_warning(f"Unknown command '{cmd}'. Type '/help' for available commands.")
            return True

    def display_welcome(self) -> None:
        """Render banner and active session info."""
        print_banner(
            title="Interactive Enterprise RAG Assistant",
            subtitle="Ask questions over ingested documents with verified citations and provenance.",
        )
        print_key_values(
            {
                "Active Provider": self.provider,
                "Active Model": self.model or "Default",
                "Prompt Strategy": self.strategy,
                "Retrieval Top-K": self.top_k,
                "Category Scope": self.category or "All Documents",
            },
            title="Session Environment",
        )
        get_console().print("[dim]Type your question, or enter '/help' to inspect available commands.[/dim]\n")

    async def execute_query(self, user_query: str) -> None:
        """Process user question through RAG stack and render response."""
        console = get_console()

        filters = SearchFilters(category=self.category) if self.category else None
        retrieval_options = SearchOptions(top_k=self.top_k)

        request = RAGRequest(
            query=user_query,
            provider=self.provider,
            model=self.model,
            prompt_strategy=self.strategy,
            filters=filters,
            retrieval_options=retrieval_options,
            conversation_history=self.history[-6:],  # Keep recent turns
        )

        response: RAGResponse | None = None

        with console.status("[bold cyan]Retrieving context & generating answer...", spinner="dots"):
            try:
                response = await self.rag_service.query(request)
            except Exception as exc:  # noqa: BLE001
                print_error(f"RAG Generation error: {exc}", exc=exc)
                return

        if response is None:
            print_error("No response generated.")
            return

        # 1. Answer Panel
        console.print()
        answer_md = Markdown(response.answer)
        provider_badge = f"[bold cyan]{response.provider}[/bold cyan]" + (f" ({response.model})" if response.model else "")
        panel = Panel(
            answer_md,
            title=f"Answer [{provider_badge}]",
            title_align="left",
            border_style="bright_blue",
            padding=(1, 2),
        )
        console.print(panel)

        # 2. Citations Panel
        if self.show_citations and response.citations:
            cit_table = Table(
                title="Verified Citations & Document Sources",
                border_style="bright_blue",
                header_style="bold cyan",
            )
            cit_table.add_column("Tag", style="bold yellow", justify="center")
            cit_table.add_column("Document ID", style="dim cyan")
            cit_table.add_column("Section / Heading", style="white")
            cit_table.add_column("Relevance Score", justify="right", style="green")

            for c in response.citations:
                cit_table.add_row(
                    c.citation_tag,
                    c.document_id[:18] + "...",
                    c.heading or "N/A",
                    f"{c.score:.4f}" if c.score else "N/A",
                )
            console.print(cit_table)

        # 3. Context Chunks Table
        if self.show_context and response.used_chunks:
            chunk_table = Table(
                title="Retrieved Knowledge Chunks in Context",
                border_style="bright_blue",
                header_style="bold cyan",
            )
            chunk_table.add_column("#", style="dim", justify="right")
            chunk_table.add_column("Score", justify="right", style="green")
            chunk_table.add_column("Tokens", justify="right", style="dim")
            chunk_table.add_column("Snippet Preview", style="white")

            for ch in response.used_chunks:
                snippet = ch.text[:100].replace("\n", " ") + "..."
                chunk_table.add_row(
                    str(ch.source_index),
                    f"{ch.score:.4f}",
                    str(ch.token_count),
                    snippet,
                )
            console.print(chunk_table)

        # 4. Metrics Telemetry Bar
        if self.show_metrics:
            m = response.metrics
            metrics_line = (
                f"[dim]Latency:[/] [bold cyan]{format_ms(m.total_duration_ms)}[/] "
                f"([dim]LLM:[/] {format_ms(m.llm_generation_duration_ms)} | "
                f"[dim]Retrieval:[/] {format_ms(m.retrieval_duration_ms)})  "
                f"[dim]Chunks:[/] [bold]{m.used_chunks_count}[/] used / {m.retrieved_chunks_count} retrieved  "
                f"[dim]Tokens:[/] [bold]{m.total_tokens}[/] ({m.prompt_tokens} in, {m.completion_tokens} out)"
            )
            console.print(Panel(metrics_line, border_style="dim bright_blue", padding=(0, 1)))

        console.print()

        # Update conversational memory
        self.history.append(LLMMessage(role=MessageRole.USER, content=user_query))
        self.history.append(LLMMessage(role=MessageRole.ASSISTANT, content=response.answer))


async def run_chat_loop(args: argparse.Namespace) -> int:
    """Start and run the interactive chat session."""
    console = get_console()

    # Initialize RAG Service through DI
    bm25_index = await build_cli_bm25_index_async()
    retrieval_service = create_cli_retrieval_service(bm25_index=bm25_index)
    rag_service = create_cli_rag_service(retrieval_service=retrieval_service)

    session = ChatSession(
        rag_service=rag_service,
        provider=args.provider,
        model=args.model,
        strategy=args.strategy,
        category=args.category,
        top_k=args.top_k,
        stream=args.stream,
    )

    session.display_welcome()

    while True:
        try:
            prompt_str = f"[bold bright_blue]Investiga[/] [[bold cyan]{session.provider}[/]] > "
            user_input = Prompt.ask(prompt_str, console=console)

            if not user_input or not user_input.strip():
                continue

            cleaned_input = user_input.strip()

            # Handle slash commands or quit
            if cleaned_input.startswith("/") or cleaned_input.lower() in ("exit", "quit", "q", "clear", "cls"):
                should_continue = session.handle_command(cleaned_input)
                if not should_continue:
                    break
                continue

            # Execute RAG query
            await session.execute_query(cleaned_input)

        except (KeyboardInterrupt, EOFError):
            console.print("\n[warning]Session interrupted. Exiting...[/warning]")
            break
        except Exception as exc:  # noqa: BLE001
            print_error(f"Unexpected chat error: {exc}", exc=exc)

    return 0


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.verbose:
        os.environ["INVESTIGA_VERBOSE"] = "1"

    try:
        exit_code = asyncio.run(run_chat_loop(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        get_console().print("\n[warning]Operation interrupted.[/warning]")
        sys.exit(130)


if __name__ == "__main__":
    main()
