"""Comprehensive Unit Tests for the Enterprise RAG Evaluation Framework.

Covers metric correctness, dataset loading/exporting, dataset building,
evaluation engine, benchmarking, report generation, exporters, analytics
DataFrame builders, evaluation history, trace viewer, run comparison,
concurrency, timeouts, and edge cases.
"""

from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.evaluation.analytics import (
    EvaluationDataFrameBuilder,
    FailureAnalysisFrame,
    GenerationMetricsFrame,
    LeaderboardFrame,
    ProviderComparisonFrame,
    QuestionAnalysisFrame,
    RetrievalMetricsFrame,
)
from app.evaluation.benchmark import RAGBenchmark
from app.evaluation.dataset import DatasetLoader, EvaluationDataset
from app.evaluation.dataset_builder import DatasetBuilder
from app.evaluation.evaluator import RAGEvaluator
from app.evaluation.exporters import EvaluationExporter
from app.evaluation.history import EvaluationHistory, TraceViewer, compare_runs
from app.evaluation.metrics import (
    GenerationMetricsCalculator,
    RetrievalMetricsCalculator,
    compute_overall_stats,
)
from app.evaluation.models import (
    BenchmarkResult,
    DifficultyLevel,
    EvaluationConfiguration,
    EvaluationRawTrace,
    EvaluationReport,
    EvaluationResult,
    EvaluationRunMetadata,
    EvaluationSample,
    GenerationMetricsResult,
    GroundTruthAnswer,
    ProviderBenchmark,
    RetrievalMetricsResult,
)
from app.evaluation.reports import ReportGenerator

# =============================================================================
# Fixtures and Helpers
# =============================================================================


def _make_sample(
    question: str = "What caused the outage?",
    expected_answer: str = "Database connection pool exhaustion.",
    expected_docs: list[str] | None = None,
    expected_keywords: list[str] | None = None,
    difficulty: str = "medium",
    category: str = "incident",
) -> EvaluationSample:
    return EvaluationSample(
        question=question,
        expected_answer=expected_answer,
        expected_documents=expected_docs or ["doc-1", "doc-2"],
        expected_keywords=expected_keywords or ["database", "connection", "pool"],
        difficulty=difficulty,
        category=category,
    )


def _make_result(
    success: bool = True,
    faithfulness: float = 0.8,
    recall_at_5: float = 0.6,
    mrr: float = 0.5,
    provider: str = "mock",
    answer_length: int = 200,
) -> EvaluationResult:
    return EvaluationResult(
        sample_id="s1",
        question="What caused the outage?",
        expected_answer="DB pool exhaustion",
        generated_answer="The outage was caused by database connection pool exhaustion [1].",
        provider=provider,
        model="mock-gpt-4",
        prompt_strategy="standard_qa",
        retrieval_metrics=RetrievalMetricsResult(
            recall_at_1=0.5,
            recall_at_3=0.5,
            recall_at_5=recall_at_5,
            recall_at_10=0.8,
            recall_at_20=1.0,
            precision_at_k=0.3,
            mrr=mrr,
            map_score=0.4,
            ndcg=0.6,
            hit_rate=1.0,
            context_precision=0.3,
            context_recall=0.6,
            avg_similarity_score=0.85,
            avg_retrieved_chunks=5.0,
            avg_retrieval_latency_ms=15.0,
        ),
        generation_metrics=GenerationMetricsResult(
            faithfulness=faithfulness,
            answer_relevancy=0.7,
            citation_coverage=0.5,
            citation_precision=0.8,
            hallucination_rate=1.0 - faithfulness,
            context_utilization=0.4,
            answer_length=answer_length,
            word_count=30,
            prompt_tokens=500,
            completion_tokens=100,
            total_tokens=600,
            llm_latency_ms=50.0,
            overall_response_time_ms=80.0,
        ),
        citations_count=2,
        retrieved_chunks_count=5,
        used_chunks_count=3,
        success=success,
        error_message=None if success else "Timeout",
        raw_trace=EvaluationRawTrace(
            question="What caused the outage?",
            provider=provider,
            model="mock-gpt-4",
            generated_answer="The outage was caused by database connection pool exhaustion [1].",
            total_latency_ms=80.0,
        ),
    )


# =============================================================================
# 1. Retrieval Metrics Tests
# =============================================================================


class TestRetrievalMetrics:
    """Tests for retrieval quality metric calculations."""

    def test_recall_at_k_perfect(self) -> None:
        retrieved = ["d1", "d2", "d3"]
        relevant = ["d1", "d2"]
        assert RetrievalMetricsCalculator.recall_at_k(retrieved, relevant, 3) == 1.0

    def test_recall_at_k_partial(self) -> None:
        retrieved = ["d1", "d3", "d4"]
        relevant = ["d1", "d2"]
        assert RetrievalMetricsCalculator.recall_at_k(retrieved, relevant, 3) == 0.5

    def test_recall_at_k_zero(self) -> None:
        retrieved = ["d3", "d4", "d5"]
        relevant = ["d1", "d2"]
        assert RetrievalMetricsCalculator.recall_at_k(retrieved, relevant, 3) == 0.0

    def test_recall_at_k_no_relevant(self) -> None:
        retrieved = ["d1", "d2"]
        relevant: list[str] = []
        assert RetrievalMetricsCalculator.recall_at_k(retrieved, relevant, 3) == 1.0

    def test_recall_at_1(self) -> None:
        retrieved = ["d2", "d1"]
        relevant = ["d1"]
        assert RetrievalMetricsCalculator.recall_at_k(retrieved, relevant, 1) == 0.0
        assert RetrievalMetricsCalculator.recall_at_k(retrieved, relevant, 2) == 1.0

    def test_precision_at_k(self) -> None:
        retrieved = ["d1", "d3", "d2", "d4"]
        relevant = ["d1", "d2"]
        assert RetrievalMetricsCalculator.precision_at_k(retrieved, relevant, 4) == 0.5

    def test_precision_at_k_zero(self) -> None:
        assert RetrievalMetricsCalculator.precision_at_k([], ["d1"], 5) == 0.0

    def test_precision_at_k_zero_k(self) -> None:
        assert RetrievalMetricsCalculator.precision_at_k(["d1"], ["d1"], 0) == 0.0

    def test_mrr_first_position(self) -> None:
        retrieved = ["d1", "d2", "d3"]
        relevant = ["d1"]
        assert RetrievalMetricsCalculator.mrr(retrieved, relevant) == 1.0

    def test_mrr_second_position(self) -> None:
        retrieved = ["d3", "d1", "d2"]
        relevant = ["d1"]
        assert RetrievalMetricsCalculator.mrr(retrieved, relevant) == 0.5

    def test_mrr_not_found(self) -> None:
        retrieved = ["d3", "d4"]
        relevant = ["d1"]
        assert RetrievalMetricsCalculator.mrr(retrieved, relevant) == 0.0

    def test_average_precision_perfect(self) -> None:
        retrieved = ["d1", "d2", "d3"]
        relevant = ["d1", "d2"]
        ap = RetrievalMetricsCalculator.average_precision(retrieved, relevant)
        # P@1 * 1 + P@2 * 1 = 1/1 + 2/2 = 2, AP = 2/2 = 1.0
        assert ap == 1.0

    def test_average_precision_partial(self) -> None:
        retrieved = ["d3", "d1", "d4", "d2"]
        relevant = ["d1", "d2"]
        ap = RetrievalMetricsCalculator.average_precision(retrieved, relevant)
        # P@2 * 1 + P@4 * 1 = 1/2 + 2/4 = 1.0, AP = 1.0/2 = 0.5
        assert ap == 0.5

    def test_average_precision_no_relevant(self) -> None:
        assert RetrievalMetricsCalculator.average_precision(["d1"], []) == 1.0

    def test_ndcg_perfect(self) -> None:
        retrieved = ["d1", "d2"]
        relevant = ["d1", "d2"]
        ndcg = RetrievalMetricsCalculator.ndcg_at_k(retrieved, relevant, 2)
        assert ndcg == pytest.approx(1.0, abs=0.001)

    def test_ndcg_imperfect(self) -> None:
        retrieved = ["d3", "d1", "d2"]
        relevant = ["d1", "d2"]
        ndcg = RetrievalMetricsCalculator.ndcg_at_k(retrieved, relevant, 3)
        # DCG = 0 + 1/log2(3) + 1/log2(4)
        # IDCG = 1/log2(2) + 1/log2(3)
        dcg = 1.0 / math.log2(3) + 1.0 / math.log2(4)
        idcg = 1.0 / math.log2(2) + 1.0 / math.log2(3)
        assert ndcg == pytest.approx(dcg / idcg, abs=0.001)

    def test_ndcg_no_relevant(self) -> None:
        assert RetrievalMetricsCalculator.ndcg_at_k(["d1"], [], 1) == 1.0

    def test_hit_rate_hit(self) -> None:
        assert RetrievalMetricsCalculator.hit_rate_at_k(["d1", "d2"], ["d2"], 2) == 1.0

    def test_hit_rate_miss(self) -> None:
        assert RetrievalMetricsCalculator.hit_rate_at_k(["d3", "d4"], ["d1"], 2) == 0.0

    def test_context_precision(self) -> None:
        retrieved = ["d1", "d3", "d2"]
        relevant = ["d1", "d2"]
        assert RetrievalMetricsCalculator.context_precision(retrieved, relevant) == pytest.approx(2 / 3, abs=0.001)

    def test_context_precision_empty(self) -> None:
        assert RetrievalMetricsCalculator.context_precision([], ["d1"]) == 0.0

    def test_context_recall(self) -> None:
        retrieved = ["d1", "d3"]
        relevant = ["d1", "d2"]
        assert RetrievalMetricsCalculator.context_recall(retrieved, relevant) == 0.5

    def test_context_recall_no_relevant(self) -> None:
        assert RetrievalMetricsCalculator.context_recall(["d1"], []) == 1.0

    def test_compute_all(self) -> None:
        result = RetrievalMetricsCalculator.compute_all(
            retrieved_ids=["d1", "d2", "d3"],
            relevant_ids=["d1", "d2"],
            scores=[0.9, 0.8, 0.7],
            retrieval_latency_ms=12.5,
        )
        assert isinstance(result, RetrievalMetricsResult)
        assert result.recall_at_5 == 1.0
        assert result.avg_similarity_score == pytest.approx(0.8, abs=0.01)
        assert result.avg_retrieval_latency_ms == 12.5


# =============================================================================
# 2. Generation Metrics Tests
# =============================================================================


class TestGenerationMetrics:
    """Tests for generation quality metric calculations."""

    def test_faithfulness_fully_grounded(self) -> None:
        answer = "The database connection pool was exhausted."
        context = ["The database connection pool was exhausted due to unclosed sessions."]
        score = GenerationMetricsCalculator.faithfulness(answer, context)
        assert score >= 0.5

    def test_faithfulness_empty_answer(self) -> None:
        assert GenerationMetricsCalculator.faithfulness("", ["context"]) == 0.0

    def test_faithfulness_empty_context(self) -> None:
        assert GenerationMetricsCalculator.faithfulness("Some answer.", []) == 0.0

    def test_answer_relevancy_with_keywords(self) -> None:
        score = GenerationMetricsCalculator.answer_relevancy(
            answer="The database pool was exhausted causing timeouts.",
            question="What caused the database issue?",
            expected_keywords=["database", "pool", "exhausted"],
        )
        assert score > 0.0

    def test_answer_relevancy_empty(self) -> None:
        assert GenerationMetricsCalculator.answer_relevancy("", "What?") == 0.0

    def test_citation_coverage(self) -> None:
        answer = "The pool was exhausted [1]. The sessions were not closed [2]. No citation here."
        score = GenerationMetricsCalculator.citation_coverage(answer)
        assert score == pytest.approx(2 / 3, abs=0.01)

    def test_citation_coverage_empty(self) -> None:
        assert GenerationMetricsCalculator.citation_coverage("") == 0.0

    def test_citation_precision_all_valid(self) -> None:
        answer = "Exhausted [1] and unclosed [2]."
        score = GenerationMetricsCalculator.citation_precision(answer, {1, 2, 3})
        assert score == 1.0

    def test_citation_precision_some_invalid(self) -> None:
        answer = "See [1] and [5]."
        score = GenerationMetricsCalculator.citation_precision(answer, {1, 2})
        assert score == 0.5

    def test_citation_precision_no_citations(self) -> None:
        assert GenerationMetricsCalculator.citation_precision("No citations.", {1}) == 0.0

    def test_hallucination_rate(self) -> None:
        assert GenerationMetricsCalculator.hallucination_rate(0.8) == pytest.approx(0.2)
        assert GenerationMetricsCalculator.hallucination_rate(1.0) == 0.0
        assert GenerationMetricsCalculator.hallucination_rate(0.0) == 1.0

    def test_context_utilization(self) -> None:
        assert GenerationMetricsCalculator.context_utilization({1, 2}, 5) == 0.4
        assert GenerationMetricsCalculator.context_utilization(set(), 5) == 0.0
        assert GenerationMetricsCalculator.context_utilization({1}, 0) == 0.0

    def test_compute_all(self) -> None:
        result = GenerationMetricsCalculator.compute_all(
            answer="The database pool was exhausted [1].",
            question="What caused the outage?",
            context_texts=["Database pool exhaustion caused the outage."],
            valid_source_indices={1, 2},
            total_context_chunks=3,
            expected_keywords=["database", "pool"],
            prompt_tokens=500,
            completion_tokens=50,
            total_tokens=550,
            llm_latency_ms=42.0,
            overall_response_time_ms=60.0,
        )
        assert isinstance(result, GenerationMetricsResult)
        assert result.prompt_tokens == 500
        assert result.total_tokens == 550
        assert result.llm_latency_ms == 42.0


# =============================================================================
# 3. Overall Statistics Tests
# =============================================================================


class TestOverallStats:
    """Tests for aggregate statistics computation."""

    def test_compute_overall_stats(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        stats = compute_overall_stats(values, "test_metric")
        assert stats["metric_name"] == "test_metric"
        assert stats["mean"] == 3.0
        assert stats["min_val"] == 1.0
        assert stats["max_val"] == 5.0
        assert stats["count"] == 5
        assert stats["p50"] == 3.0

    def test_compute_overall_stats_empty(self) -> None:
        stats = compute_overall_stats([], "empty")
        assert stats["count"] == 0
        assert stats["mean"] == 0.0

    def test_compute_overall_stats_single(self) -> None:
        stats = compute_overall_stats([42.0], "single")
        assert stats["mean"] == 42.0
        assert stats["std"] == 0.0
        assert stats["p50"] == 42.0


# =============================================================================
# 4. Dataset Loading Tests
# =============================================================================


class TestDatasetLoading:
    """Tests for dataset loading from JSON, JSONL, and CSV."""

    def test_load_json_string(self) -> None:
        data = json.dumps([
            {"question": "Q1?", "expected_answer": "A1"},
            {"question": "Q2?", "expected_answer": "A2"},
        ])
        samples = DatasetLoader.load_json(data)
        assert len(samples) == 2
        assert samples[0].question == "Q1?"

    def test_load_jsonl_string(self) -> None:
        lines = '{"question": "Q1?"}\n{"question": "Q2?"}'
        samples = DatasetLoader.load_jsonl(lines)
        assert len(samples) == 2

    def test_load_csv_string(self) -> None:
        csv_data = "question,expected_answer,difficulty,category\nQ1?,A1,easy,security\nQ2?,A2,hard,network"
        samples = DatasetLoader.load_csv(csv_data)
        assert len(samples) == 2
        assert samples[0].difficulty == "easy"
        assert samples[1].category == "network"

    def test_load_csv_with_pipe_delimited_lists(self) -> None:
        csv_data = "question,expected_documents,expected_keywords\nQ1?,doc1|doc2,key1|key2"
        samples = DatasetLoader.load_csv(csv_data)
        assert samples[0].expected_documents == ["doc1", "doc2"]
        assert samples[0].expected_keywords == ["key1", "key2"]

    def test_load_json_file(self, tmp_path: Path) -> None:
        data = [{"question": "From file?", "expected_answer": "Yes"}]
        path = tmp_path / "test.json"
        path.write_text(json.dumps(data))
        samples = DatasetLoader.load_json(path)
        assert len(samples) == 1

    def test_load_json_with_alternative_keys(self) -> None:
        data = json.dumps([{"query": "Alt query?", "ground_truth": "Alt answer"}])
        samples = DatasetLoader.load_json(data)
        assert samples[0].question == "Alt query?"
        assert samples[0].expected_answer == "Alt answer"


# =============================================================================
# 5. Dataset Container Tests
# =============================================================================


class TestEvaluationDataset:
    """Tests for EvaluationDataset container."""

    def test_filter_by_category(self) -> None:
        samples = [
            _make_sample(category="security"),
            _make_sample(question="Q2?", category="network"),
            _make_sample(question="Q3?", category="security"),
        ]
        ds = EvaluationDataset(samples, name="test")
        filtered = ds.filter_by_category("security")
        assert len(filtered) == 2

    def test_filter_by_difficulty(self) -> None:
        samples = [
            _make_sample(difficulty="easy"),
            _make_sample(question="Q2?", difficulty="hard"),
        ]
        ds = EvaluationDataset(samples)
        assert len(ds.filter_by_difficulty("easy")) == 1

    def test_sample(self) -> None:
        samples = [_make_sample(question=f"Q{i}?") for i in range(20)]
        ds = EvaluationDataset(samples)
        sampled = ds.sample(5, seed=42)
        assert len(sampled) == 5

    def test_statistics(self) -> None:
        samples = [
            _make_sample(category="sec", difficulty="easy"),
            _make_sample(question="Q2?", category="net", difficulty="hard"),
        ]
        ds = EvaluationDataset(samples, name="stats_test")
        stats = ds.statistics()
        assert stats["total_samples"] == 2
        assert "sec" in stats["categories"]
        assert "easy" in stats["difficulties"]

    def test_export_roundtrip_json(self) -> None:
        samples = [_make_sample()]
        ds = EvaluationDataset(samples)
        json_str = ds.to_json()
        reloaded = DatasetLoader.load_json(json_str)
        assert len(reloaded) == 1
        assert reloaded[0].question == samples[0].question

    def test_export_roundtrip_jsonl(self) -> None:
        samples = [_make_sample(), _make_sample(question="Q2?")]
        ds = EvaluationDataset(samples)
        jsonl_str = ds.to_jsonl()
        reloaded = DatasetLoader.load_jsonl(jsonl_str)
        assert len(reloaded) == 2

    def test_export_roundtrip_csv(self) -> None:
        samples = [_make_sample()]
        ds = EvaluationDataset(samples)
        csv_str = ds.to_csv()
        reloaded = DatasetLoader.load_csv(csv_str)
        assert len(reloaded) == 1


# =============================================================================
# 6. Dataset Builder Tests
# =============================================================================


class TestDatasetBuilder:
    """Tests for benchmark dataset builder."""

    def test_create_sample(self) -> None:
        builder = DatasetBuilder()
        sample = builder.create_sample(
            question="What is the runbook for?",
            expected_answer="Database failover",
            expected_documents=["doc-1"],
        )
        assert sample.question == "What is the runbook for?"
        assert len(builder.samples) == 1

    def test_from_document_metadata(self) -> None:
        builder = DatasetBuilder()
        generated = builder.from_document_metadata(
            document_id="doc-123",
            title="Database Failover Runbook",
            category="runbook",
            description="Procedures for database failover.",
            tags=["database", "failover", "recovery"],
        )
        assert len(generated) == 3  # Title Q + Summary Q + Tags Q
        assert len(builder.samples) == 3

    def test_from_chunks(self) -> None:
        builder = DatasetBuilder()
        chunks = [
            {"text": "Connection pooling is critical for performance.", "heading": "Connection Pooling"},
            {"text": "Short.", "heading": ""},
            {"text": "Monitoring alerts should be configured for CPU thresholds.", "heading": "Monitoring"},
        ]
        generated = builder.from_chunks("doc-1", chunks)
        assert len(generated) >= 2  # "Short." will be skipped

    def test_build_dataset(self) -> None:
        builder = DatasetBuilder()
        builder.create_sample(question="Q1?")
        builder.create_sample(question="Q2?")
        ds = builder.build(name="my_dataset")
        assert len(ds) == 2
        assert ds.name == "my_dataset"

    def test_clear(self) -> None:
        builder = DatasetBuilder()
        builder.create_sample(question="Q1?")
        builder.clear()
        assert len(builder.samples) == 0


# =============================================================================
# 7. Models Tests
# =============================================================================


class TestModels:
    """Tests for evaluation Pydantic models."""

    def test_evaluation_sample_creation(self) -> None:
        sample = _make_sample()
        assert sample.question == "What caused the outage?"
        assert sample.difficulty == "medium"

    def test_ground_truth_answer(self) -> None:
        gt = GroundTruthAnswer(
            answer_text="DB pool exhaustion.",
            key_facts=["pool", "exhaustion"],
            required_citations=["doc-1"],
            forbidden_terms=["alien"],
        )
        assert len(gt.key_facts) == 2

    def test_difficulty_level_enum(self) -> None:
        assert DifficultyLevel.EASY == "easy"
        assert DifficultyLevel.EXPERT == "expert"

    def test_evaluation_configuration_defaults(self) -> None:
        config = EvaluationConfiguration()
        assert config.max_concurrency == 5
        assert config.timeout_seconds == 60.0
        assert 1 in config.k_values
        assert 20 in config.k_values

    def test_evaluation_result_success(self) -> None:
        result = _make_result()
        assert result.success is True
        assert result.provider == "mock"

    def test_evaluation_result_failure(self) -> None:
        result = _make_result(success=False)
        assert result.success is False


# =============================================================================
# 8. Evaluator Tests (Mock RAGService)
# =============================================================================


def _create_mock_rag_response() -> MagicMock:
    """Create a mock RAGResponse for evaluator tests."""
    from app.rag.models import (
        Citation,
        ContextChunk,
        RAGMetrics,
        RAGTrace,
    )
    from app.retrieval.models import RetrievalResult

    chunk = ContextChunk(
        source_index=1,
        citation_tag="[1]",
        chunk_id="c1",
        document_id="doc-1",
        text="Database pool exhaustion occurred.",
        token_count=10,
        score=0.9,
    )

    citation = Citation(
        source_index=1,
        citation_tag="[1]",
        chunk_id="c1",
        document_id="doc-1",
        score=0.9,
        snippet="Database pool exhaustion occurred.",
    )

    metrics = RAGMetrics(
        retrieval_duration_ms=10.0,
        context_build_duration_ms=2.0,
        prompt_build_duration_ms=1.0,
        llm_generation_duration_ms=30.0,
        citations_duration_ms=1.0,
        total_duration_ms=50.0,
        retrieved_chunks_count=3,
        used_chunks_count=1,
        citations_count=1,
        prompt_tokens=400,
        completion_tokens=80,
        total_tokens=480,
    )

    trace = RAGTrace(
        query="What caused the outage?",
        provider="mock",
        model="mock-gpt-4",
        prompt_strategy="standard_qa",
    )

    retrieval_result = MagicMock(spec=RetrievalResult)
    retrieval_result.chunks = [MagicMock(document_id="doc-1", chunk_id="c1", score=0.9)]

    response = MagicMock()
    response.answer = "Database pool exhaustion caused the outage [1]."
    response.citations = [citation]
    response.used_chunks = [chunk]
    response.retrieval_result = retrieval_result
    response.metrics = metrics
    response.trace = trace
    response.provider = "mock"
    response.model = "mock-gpt-4"
    response.prompt_strategy = "standard_qa"

    return response


class TestEvaluator:
    """Tests for RAGEvaluator."""

    @pytest.fixture()
    def mock_rag_service(self) -> MagicMock:
        service = MagicMock()
        service.query = AsyncMock(return_value=_create_mock_rag_response())
        return service

    @pytest.mark.asyncio()
    async def test_evaluate_sample(self, mock_rag_service: MagicMock) -> None:
        evaluator = RAGEvaluator(mock_rag_service)
        sample = _make_sample()
        config = EvaluationConfiguration()

        result = await evaluator.evaluate_sample(sample, config)

        assert result.success is True
        assert result.provider == "mock"
        assert result.retrieval_metrics.recall_at_5 >= 0.0
        assert result.generation_metrics.faithfulness >= 0.0

    @pytest.mark.asyncio()
    async def test_evaluate_sample_failure(self) -> None:
        service = MagicMock()
        service.query = AsyncMock(side_effect=RuntimeError("Provider error"))
        evaluator = RAGEvaluator(service)

        result = await evaluator.evaluate_sample(
            _make_sample(), EvaluationConfiguration()
        )
        assert result.success is False
        assert "Provider error" in (result.error_message or "")

    @pytest.mark.asyncio()
    async def test_evaluate_dataset(self, mock_rag_service: MagicMock) -> None:
        evaluator = RAGEvaluator(mock_rag_service)
        samples = [_make_sample(question=f"Q{i}?") for i in range(5)]
        config = EvaluationConfiguration(max_concurrency=2)

        report = await evaluator.evaluate_dataset(samples, config)

        assert isinstance(report, EvaluationReport)
        assert report.run_metadata.total_samples == 5
        assert report.run_metadata.successful_samples == 5
        assert len(report.results) == 5

    @pytest.mark.asyncio()
    async def test_evaluate_dataset_with_timeout(self) -> None:
        async def slow_query(*args: object, **kwargs: object) -> MagicMock:
            await asyncio.sleep(10)
            return _create_mock_rag_response()

        service = MagicMock()
        service.query = slow_query
        evaluator = RAGEvaluator(service)
        config = EvaluationConfiguration(timeout_seconds=1.0, max_concurrency=1)

        report = await evaluator.evaluate_dataset([_make_sample()], config)

        assert report.run_metadata.failed_samples == 1
        assert "Timeout" in (report.results[0].error_message or "")

    @pytest.mark.asyncio()
    async def test_evaluate_empty_dataset(self, mock_rag_service: MagicMock) -> None:
        evaluator = RAGEvaluator(mock_rag_service)
        report = await evaluator.evaluate_dataset([], EvaluationConfiguration())
        assert report.run_metadata.total_samples == 0
        assert len(report.results) == 0


# =============================================================================
# 9. Benchmark Tests
# =============================================================================


class TestBenchmark:
    """Tests for multi-provider benchmarking."""

    @pytest.fixture()
    def mock_rag_service(self) -> MagicMock:
        service = MagicMock()
        service.query = AsyncMock(return_value=_create_mock_rag_response())
        return service

    @pytest.mark.asyncio()
    async def test_benchmark_single_provider(self, mock_rag_service: MagicMock) -> None:
        evaluator = RAGEvaluator(mock_rag_service)
        benchmark = RAGBenchmark(evaluator, providers=["mock"])
        samples = [_make_sample(question=f"Q{i}?") for i in range(3)]
        config = EvaluationConfiguration(max_concurrency=2)

        result = await benchmark.run(samples, config)

        assert isinstance(result, BenchmarkResult)
        assert len(result.providers) == 1
        assert result.providers[0].provider_name == "mock"
        assert len(result.leaderboard) == 1
        assert result.leaderboard[0]["rank"] == 1

    @pytest.mark.asyncio()
    async def test_benchmark_multi_provider(self, mock_rag_service: MagicMock) -> None:
        evaluator = RAGEvaluator(mock_rag_service)
        benchmark = RAGBenchmark(evaluator, providers=["mock", "gemini"])
        samples = [_make_sample()]
        config = EvaluationConfiguration()

        result = await benchmark.run(samples, config)

        assert len(result.providers) == 2
        assert len(result.leaderboard) == 2
        assert result.leaderboard[0]["rank"] == 1
        assert result.leaderboard[1]["rank"] == 2

    @pytest.mark.asyncio()
    async def test_benchmark_leaderboard_has_composite_score(
        self, mock_rag_service: MagicMock,
    ) -> None:
        evaluator = RAGEvaluator(mock_rag_service)
        benchmark = RAGBenchmark(evaluator, providers=["mock"])
        result = await benchmark.run([_make_sample()], EvaluationConfiguration())

        assert "composite_score" in result.leaderboard[0]
        assert result.leaderboard[0]["composite_score"] >= 0.0


# =============================================================================
# 10. Report Generation Tests
# =============================================================================


class TestReports:
    """Tests for report generation."""

    def test_generate_markdown(self) -> None:
        report = EvaluationReport(
            run_metadata=EvaluationRunMetadata(total_samples=2, successful_samples=2),
            results=[_make_result(), _make_result()],
            summary={"avg_faithfulness": 0.8, "avg_recall_at_5": 0.6},
        )
        md = ReportGenerator.generate_markdown(report)
        assert "# RAG Evaluation Report" in md
        assert "Summary Statistics" in md

    def test_generate_benchmark_markdown(self) -> None:
        benchmark = BenchmarkResult(
            providers=[
                ProviderBenchmark(provider_name="mock", composite_score=0.8),
                ProviderBenchmark(provider_name="gemini", composite_score=0.7),
            ],
            leaderboard=[
                {"rank": 1, "provider": "mock", "model": "", "composite_score": 0.8,
                 "avg_faithfulness": 0.8, "avg_hallucination_rate": 0.2,
                 "avg_citation_coverage": 0.6, "avg_recall_at_5": 0.7,
                 "avg_latency_ms": 50.0, "avg_answer_relevancy": 0.7,
                 "avg_token_usage": 500, "total_samples": 5, "successful_samples": 5},
            ],
        )
        md = ReportGenerator.generate_benchmark_markdown(benchmark)
        assert "Leaderboard" in md

    def test_generate_summary_stats(self) -> None:
        results = [_make_result(), _make_result(faithfulness=0.9)]
        stats = ReportGenerator.generate_summary_stats(results)
        assert len(stats) > 0
        assert any(s.metric_name == "faithfulness" for s in stats)

    def test_markdown_with_failures(self) -> None:
        report = EvaluationReport(
            results=[_make_result(success=False)],
            summary={},
        )
        md = ReportGenerator.generate_markdown(report)
        assert "Failed Questions" in md


# =============================================================================
# 11. Exporter Tests
# =============================================================================


class TestExporters:
    """Tests for evaluation exporters."""

    def test_to_json(self) -> None:
        report = EvaluationReport(results=[_make_result()])
        json_str = EvaluationExporter.to_json(report)
        data = json.loads(json_str)
        assert "results" in data
        assert len(data["results"]) == 1

    def test_to_csv(self) -> None:
        report = EvaluationReport(results=[_make_result()])
        csv_str = EvaluationExporter.to_csv(report)
        assert "sample_id" in csv_str
        assert "faithfulness" in csv_str

    def test_to_markdown(self) -> None:
        report = EvaluationReport(results=[_make_result()])
        md = EvaluationExporter.to_markdown(report)
        assert "# RAG Evaluation Report" in md

    def test_to_json_file(self, tmp_path: Path) -> None:
        report = EvaluationReport(results=[_make_result()])
        path = tmp_path / "report.json"
        EvaluationExporter.to_json(report, path)
        assert path.exists()
        data = json.loads(path.read_text())
        assert "results" in data

    def test_to_csv_file(self, tmp_path: Path) -> None:
        report = EvaluationReport(results=[_make_result()])
        path = tmp_path / "metrics.csv"
        EvaluationExporter.to_csv(report, path)
        assert path.exists()

    def test_export_benchmark(self, tmp_path: Path) -> None:
        benchmark = BenchmarkResult(
            providers=[ProviderBenchmark(provider_name="mock")],
            leaderboard=[{"rank": 1, "provider": "mock", "composite_score": 0.5}],
        )
        artifacts = EvaluationExporter.export_benchmark(benchmark, tmp_path / "bench")
        assert "benchmark.json" in artifacts
        assert "benchmark.md" in artifacts


# =============================================================================
# 12. Analytics DataFrame Tests
# =============================================================================


class TestAnalytics:
    """Tests for analytics DataFrame builders."""

    def test_results_dataframe(self) -> None:
        results = [_make_result(), _make_result()]
        df = EvaluationDataFrameBuilder.results_to_dataframe(results)
        # Works as dict or DataFrame
        if isinstance(df, dict):
            assert len(df["sample_id"]) == 2
            assert "faithfulness" in df
        else:
            assert len(df) == 2

    def test_provider_comparison_frame(self) -> None:
        benchmark = BenchmarkResult(
            providers=[
                ProviderBenchmark(provider_name="mock"),
                ProviderBenchmark(provider_name="gemini"),
            ],
        )
        df = ProviderComparisonFrame.benchmark_to_dataframe(benchmark)
        if isinstance(df, dict):
            assert len(df["provider"]) == 2
        else:
            assert len(df) == 2

    def test_leaderboard_frame(self) -> None:
        benchmark = BenchmarkResult(
            leaderboard=[
                {"rank": 1, "provider": "mock", "composite_score": 0.8},
                {"rank": 2, "provider": "gemini", "composite_score": 0.6},
            ],
        )
        df = LeaderboardFrame.to_dataframe(benchmark)
        if isinstance(df, dict):
            assert len(df["rank"]) == 2

    def test_leaderboard_frame_empty(self) -> None:
        benchmark = BenchmarkResult()
        df = LeaderboardFrame.to_dataframe(benchmark)
        if isinstance(df, dict):
            assert len(df["rank"]) == 0

    def test_retrieval_metrics_frame(self) -> None:
        results = [_make_result()]
        df = RetrievalMetricsFrame.to_dataframe(results)
        if isinstance(df, dict):
            assert "recall_at_5" in df

    def test_generation_metrics_frame(self) -> None:
        results = [_make_result()]
        df = GenerationMetricsFrame.to_dataframe(results)
        if isinstance(df, dict):
            assert "faithfulness" in df

    def test_question_analysis_frame(self) -> None:
        results = [_make_result()]
        df = QuestionAnalysisFrame.to_dataframe(results)
        if isinstance(df, dict):
            assert "question" in df

    def test_failure_analysis_frame(self) -> None:
        results = [_make_result(success=False), _make_result()]
        df = FailureAnalysisFrame.to_dataframe(results)
        if isinstance(df, dict):
            assert len(df["sample_id"]) == 1


# =============================================================================
# 13. History Tests
# =============================================================================


class TestHistory:
    """Tests for evaluation history and trace viewer."""

    def test_save_and_list_runs(self, tmp_path: Path) -> None:
        history = EvaluationHistory(base_dir=tmp_path / "runs")
        report = EvaluationReport(
            run_metadata=EvaluationRunMetadata(total_samples=1),
            results=[_make_result()],
            summary={"avg_faithfulness": 0.8},
        )
        run_dir = history.save_run(report)
        assert run_dir.exists()
        assert (run_dir / "report.md").exists()
        assert (run_dir / "report.json").exists()
        assert (run_dir / "metrics.csv").exists()
        assert (run_dir / "trace.json").exists()

        runs = history.list_runs()
        assert len(runs) == 1

    def test_load_run(self, tmp_path: Path) -> None:
        history = EvaluationHistory(base_dir=tmp_path / "runs")
        report = EvaluationReport(
            run_metadata=EvaluationRunMetadata(total_samples=1),
            results=[_make_result()],
        )
        run_dir = history.save_run(report)

        # Load by directory name
        loaded = history.load_run(run_dir.name)
        assert loaded is not None
        assert len(loaded.results) == 1

    def test_load_run_not_found(self, tmp_path: Path) -> None:
        history = EvaluationHistory(base_dir=tmp_path / "runs")
        assert history.load_run("nonexistent") is None

    def test_save_with_benchmark(self, tmp_path: Path) -> None:
        history = EvaluationHistory(base_dir=tmp_path / "runs")
        report = EvaluationReport(results=[_make_result()])
        benchmark = BenchmarkResult(
            providers=[ProviderBenchmark(provider_name="mock")],
            leaderboard=[{"rank": 1, "provider": "mock", "composite_score": 0.5}],
        )
        run_dir = history.save_run(report, benchmark)
        assert (run_dir / "benchmark.json").exists()
        assert (run_dir / "benchmark.md").exists()


# =============================================================================
# 14. Trace Viewer Tests
# =============================================================================


class TestTraceViewer:
    """Tests for TraceViewer utility."""

    def test_view_trace(self, tmp_path: Path) -> None:
        history = EvaluationHistory(base_dir=tmp_path / "runs")
        result = _make_result()
        report = EvaluationReport(results=[result])
        run_dir = history.save_run(report)

        viewer = TraceViewer(history)
        trace = viewer.view_trace(run_dir.name, result.sample_id)

        assert trace is not None
        assert trace["question"] == result.question
        assert trace["success"] is True
        assert "retrieval_metrics" in trace
        assert "generation_metrics" in trace
        assert "latency_breakdown" in trace

    def test_view_all_traces(self, tmp_path: Path) -> None:
        history = EvaluationHistory(base_dir=tmp_path / "runs")
        report = EvaluationReport(results=[_make_result(), _make_result()])
        run_dir = history.save_run(report)

        viewer = TraceViewer(history)
        traces = viewer.view_all_traces(run_dir.name)
        assert len(traces) == 2

    def test_view_failures(self, tmp_path: Path) -> None:
        history = EvaluationHistory(base_dir=tmp_path / "runs")
        report = EvaluationReport(results=[_make_result(), _make_result(success=False)])
        run_dir = history.save_run(report)

        viewer = TraceViewer(history)
        failures = viewer.view_failures(run_dir.name)
        assert len(failures) == 1

    def test_view_trace_not_found(self, tmp_path: Path) -> None:
        history = EvaluationHistory(base_dir=tmp_path / "runs")
        viewer = TraceViewer(history)
        assert viewer.view_trace("nonexistent", "s1") is None


# =============================================================================
# 15. Run Comparison Tests
# =============================================================================


class TestRunComparison:
    """Tests for compare_runs functionality."""

    def test_compare_two_runs(self, tmp_path: Path) -> None:
        history = EvaluationHistory(base_dir=tmp_path / "runs")

        r1 = EvaluationReport(
            run_metadata=EvaluationRunMetadata(provider="mock"),
            results=[_make_result(faithfulness=0.7)],
            summary={"avg_faithfulness": 0.7, "avg_recall_at_5": 0.5, "avg_mrr": 0.4,
                     "avg_hallucination_rate": 0.3, "avg_latency_ms": 100.0,
                     "avg_citation_coverage": 0.5},
        )
        dir1 = history.save_run(r1)

        r2 = EvaluationReport(
            run_metadata=EvaluationRunMetadata(provider="gemini"),
            results=[_make_result(faithfulness=0.9)],
            summary={"avg_faithfulness": 0.9, "avg_recall_at_5": 0.7, "avg_mrr": 0.6,
                     "avg_hallucination_rate": 0.1, "avg_latency_ms": 80.0,
                     "avg_citation_coverage": 0.7},
        )
        dir2 = history.save_run(r2)

        comparison = compare_runs(history, [dir1.name, dir2.name])

        assert comparison["total_compared"] == 2
        assert len(comparison["runs"]) == 2
        assert len(comparison["deltas"]) == 1
        delta = comparison["deltas"][0]
        assert delta["avg_faithfulness_delta"] == pytest.approx(0.2, abs=0.01)

    def test_compare_with_missing_run(self, tmp_path: Path) -> None:
        history = EvaluationHistory(base_dir=tmp_path / "runs")
        comparison = compare_runs(history, ["nonexistent"])
        assert comparison["runs"][0]["status"] == "not_found"


# =============================================================================
# 16. Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_dataset_loading(self) -> None:
        samples = DatasetLoader.load_json("[]")
        assert len(samples) == 0

    def test_malformed_json(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            DatasetLoader.load_json("{invalid json")

    def test_no_retrieval_results(self) -> None:
        result = RetrievalMetricsCalculator.compute_all(
            retrieved_ids=[],
            relevant_ids=["d1"],
            scores=[],
            retrieval_latency_ms=0.0,
        )
        assert result.recall_at_5 == 0.0
        assert result.mrr == 0.0

    def test_missing_citations_in_answer(self) -> None:
        result = GenerationMetricsCalculator.compute_all(
            answer="No citations here.",
            question="What happened?",
            context_texts=["Context text."],
            valid_source_indices={1, 2},
            total_context_chunks=2,
        )
        assert result.citation_coverage == 0.0
        assert result.citation_precision == 0.0
        assert result.context_utilization == 0.0

    def test_report_generation_empty_results(self) -> None:
        report = EvaluationReport(results=[])
        md = ReportGenerator.generate_markdown(report)
        assert "# RAG Evaluation Report" in md

    def test_dataset_to_file(self, tmp_path: Path) -> None:
        ds = EvaluationDataset([_make_sample()], name="file_test")
        json_path = tmp_path / "test.json"
        ds.to_json(json_path)
        assert json_path.exists()

        csv_path = tmp_path / "test.csv"
        ds.to_csv(csv_path)
        assert csv_path.exists()

        jsonl_path = tmp_path / "test.jsonl"
        ds.to_jsonl(jsonl_path)
        assert jsonl_path.exists()
