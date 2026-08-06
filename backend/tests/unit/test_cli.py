"""Unit tests for Investiga Operational CLI."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Ensure scripts and backend in path
_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parents[2] if "backend" in str(_TESTS_DIR) else _TESTS_DIR.parents[1]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_BACKEND_DIR = _REPO_ROOT / "backend"

for _p in [str(_REPO_ROOT), str(_BACKEND_DIR), str(_SCRIPTS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts.common.factory import (
    MockEmbeddingProvider,
    create_cli_benchmark,
    create_cli_embedding_service,
    create_cli_evaluator,
    create_cli_rag_service,
    create_cli_retrieval_service,
    create_cli_vector_repository,
    get_cli_settings,
)
from scripts.common.helpers import (
    format_bytes,
    format_duration,
    format_ms,
    format_pct,
    format_score,
    resolve_path,
)
from scripts.chat import ChatSession, build_parser as build_chat_parser
from scripts.ingest_knowledge import build_parser as build_ingest_parser
from scripts.run_evaluation import (
    _find_metric,
    _get_default_benchmark_samples,
    _parse_k_values,
    build_parser as build_eval_parser,
)
from scripts.benchmark_providers import (
    _parse_providers,
    build_parser as build_bench_parser,
)


class TestHelpers:
    """Test CLI formatting and path resolution helpers."""

    def test_format_bytes(self) -> None:
        assert format_bytes(500) == "500 B"
        assert format_bytes(1024) == "1.0 KB"
        assert format_bytes(1024 * 1024) == "1.0 MB"
        assert format_bytes(1024 * 1024 * 1024) == "1.0 GB"

    def test_format_duration(self) -> None:
        assert format_duration(30.5) == "30.50s"
        assert format_duration(90.0) == "1m 30.0s"
        assert format_duration(3665.0) == "1h 1m"

    def test_format_ms(self) -> None:
        assert format_ms(15.2) == "15.2ms"
        assert format_ms(2500.0) == "2.50s"

    def test_format_score(self) -> None:
        assert format_score(0.85432) == "0.8543"

    def test_format_pct(self) -> None:
        assert format_pct(0.854) == "85.4%"

    def test_resolve_path(self) -> None:
        p = resolve_path("scripts/chat.py")
        assert p.is_absolute()
        assert p.name == "chat.py"


class TestMockEmbeddingProvider:
    """Test deterministic mock embedding provider."""

    def test_embedding_generation(self) -> None:
        provider = MockEmbeddingProvider(dimension=768)
        assert provider.dimension == 768
        assert provider.model_name == "mock-bge-base-en"

        vecs = provider.encode_batch(["hello world", "test query"])
        assert vecs.shape == (2, 768)
        norm0 = float((vecs[0] ** 2).sum() ** 0.5)
        assert abs(norm0 - 1.0) < 1e-4

        vecs_again = provider.encode_batch(["hello world"])
        assert (vecs[0] == vecs_again[0]).all()


class TestFactoryContainer:
    """Test dependency injection factory wiring."""

    def test_settings_retrieval(self) -> None:
        settings = get_cli_settings()
        assert settings is not None
        assert settings.app.name == "Investiga"

    def test_create_embedding_service(self) -> None:
        mock_provider = MockEmbeddingProvider(dimension=768)
        from app.embeddings.embedding_service import EmbeddingService
        svc = EmbeddingService(provider=mock_provider)
        assert svc is not None

    def test_create_vector_repository(self) -> None:
        repo = create_cli_vector_repository()
        assert repo is not None

    def test_create_retrieval_service(self) -> None:
        mock_provider = MockEmbeddingProvider(dimension=768)
        from app.embeddings.embedding_service import EmbeddingService
        emb_svc = EmbeddingService(provider=mock_provider)
        ret_svc = create_cli_retrieval_service(embedding_service=emb_svc)
        assert ret_svc is not None

    def test_create_rag_service(self) -> None:
        mock_provider = MockEmbeddingProvider(dimension=768)
        from app.embeddings.embedding_service import EmbeddingService
        emb_svc = EmbeddingService(provider=mock_provider)
        ret_svc = create_cli_retrieval_service(embedding_service=emb_svc)
        rag_svc = create_cli_rag_service(retrieval_service=ret_svc)
        assert rag_svc is not None

    def test_create_evaluator(self) -> None:
        mock_rag = MagicMock()
        evaluator = create_cli_evaluator(rag_service=mock_rag)
        assert evaluator is not None

    def test_create_benchmark(self) -> None:
        mock_evaluator = MagicMock()
        benchmark = create_cli_benchmark(evaluator=mock_evaluator, providers=["mock"])
        assert benchmark is not None
        assert benchmark.providers == ["mock"]


class TestIngestKnowledgeCLI:
    """Test ingest_knowledge.py CLI parsing and behaviors."""

    def test_argument_parser(self) -> None:
        parser = build_ingest_parser()
        args = parser.parse_args(["--source", "docs", "--batch-size", "25", "--dry-run"])
        assert args.source == "docs"
        assert args.batch_size == 25
        assert args.dry_run is True
        assert args.recursive is True

    def test_argument_parser_category(self) -> None:
        parser = build_ingest_parser()
        args = parser.parse_args(["-s", "docs", "-c", "Engineering", "--no-recursive"])
        assert args.source == "docs"
        assert args.category == "Engineering"
        assert args.recursive is False


class TestChatCLI:
    """Test chat.py CLI parsing and interactive session commands."""

    def test_chat_parser(self) -> None:
        parser = build_chat_parser()
        args = parser.parse_args(["--provider", "mock", "--strategy", "concise", "--top-k", "8"])
        assert args.provider == "mock"
        assert args.strategy == "concise"
        assert args.top_k == 8

    def test_chat_session_commands(self) -> None:
        mock_rag = MagicMock()
        session = ChatSession(
            rag_service=mock_rag,
            provider="mock",
            strategy="standard_qa",
        )

        # /provider command
        assert session.handle_command("/provider ollama llama3") is True
        assert session.provider == "ollama"
        assert session.model == "llama3"

        # /strategy command
        assert session.handle_command("/strategy executive_summary") is True
        assert session.strategy == "executive_summary"

        # /context toggle
        assert session.show_context is False
        assert session.handle_command("/context") is True
        assert session.show_context is True

        # /citations toggle
        assert session.show_citations is True
        assert session.handle_command("/citations") is True
        assert session.show_citations is False

        # /metrics toggle
        assert session.show_metrics is True
        assert session.handle_command("/metrics") is True
        assert session.show_metrics is False

        # Exit command
        assert session.handle_command("exit") is False
        assert session.handle_command("quit") is False
        assert session.handle_command("q") is False


class TestRunEvaluationCLI:
    """Test run_evaluation.py CLI parsing and helpers."""

    def test_eval_parser(self) -> None:
        parser = build_eval_parser()
        args = parser.parse_args(["--provider", "mock", "--k-values", "1,5,10", "--concurrency", "8"])
        assert args.provider == "mock"
        assert args.k_values == "1,5,10"
        assert args.concurrency == 8

    def test_k_values_parser(self) -> None:
        assert _parse_k_values("1, 3, 5, 10") == [1, 3, 5, 10]
        assert _parse_k_values("invalid") == [1, 3, 5, 10]

    def test_default_samples(self) -> None:
        samples = _get_default_benchmark_samples()
        assert len(samples) >= 4
        for s in samples:
            assert s.question
            assert s.difficulty in ("easy", "medium", "hard", "expert")


class TestBenchmarkProvidersCLI:
    """Test benchmark_providers.py CLI parsing and provider resolution."""

    def test_bench_parser(self) -> None:
        parser = build_bench_parser()
        args = parser.parse_args(["--providers", "mock,gemini", "--concurrency", "2"])
        assert args.providers == "mock,gemini"
        assert args.concurrency == 2

    def test_parse_providers(self) -> None:
        assert _parse_providers("mock,gemini") == ["mock", "gemini"]
        assert _parse_providers("all") == ["mock", "gemini", "ollama"]
        assert _parse_providers("unknown") == ["mock"]
