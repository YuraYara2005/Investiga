"""Evaluation Domain Models for the Enterprise RAG Evaluation Framework.

Defines strongly-typed Pydantic v2 models for evaluation samples, ground-truth answers,
retrieval/generation quality metrics, evaluation results, reports, benchmarks,
run metadata, and configuration.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DifficultyLevel(StrEnum):
    """Difficulty classification for benchmark evaluation samples."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class EvaluationSample(BaseModel):
    """A single benchmark evaluation question with ground-truth expectations."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique sample identifier.",
    )
    question: str = Field(
        ...,
        min_length=1,
        description="Benchmark question to evaluate.",
    )
    expected_answer: str = Field(
        default="",
        description="Expected or reference answer for comparison.",
    )
    expected_documents: list[str] = Field(
        default_factory=list,
        description="List of expected document IDs that should be retrieved.",
    )
    expected_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords expected in a correct answer.",
    )
    difficulty: str = Field(
        default=DifficultyLevel.MEDIUM,
        description="Difficulty classification (easy, medium, hard, expert).",
    )
    category: str = Field(
        default="general",
        description="Category or domain of the question.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary additional metadata for the sample.",
    )


class GroundTruthAnswer(BaseModel):
    """Ground-truth reference answer with key facts for faithfulness checking."""

    model_config = ConfigDict(frozen=True)

    answer_text: str = Field(
        ...,
        description="Full reference answer text.",
    )
    key_facts: list[str] = Field(
        default_factory=list,
        description="Individual factual statements that must be present.",
    )
    required_citations: list[str] = Field(
        default_factory=list,
        description="Document IDs that must be cited.",
    )
    forbidden_terms: list[str] = Field(
        default_factory=list,
        description="Terms that indicate hallucination if present.",
    )


class RetrievalMetricsResult(BaseModel):
    """Computed retrieval quality metrics for an evaluated sample."""

    model_config = ConfigDict(frozen=True)

    recall_at_1: float = Field(default=0.0, ge=0.0, le=1.0)
    recall_at_3: float = Field(default=0.0, ge=0.0, le=1.0)
    recall_at_5: float = Field(default=0.0, ge=0.0, le=1.0)
    recall_at_10: float = Field(default=0.0, ge=0.0, le=1.0)
    recall_at_20: float = Field(default=0.0, ge=0.0, le=1.0)
    precision_at_k: float = Field(default=0.0, ge=0.0, le=1.0)
    mrr: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Mean Reciprocal Rank.",
    )
    map_score: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Mean Average Precision.",
    )
    ndcg: float = Field(
        default=0.0, ge=0.0,
        description="Normalized Discounted Cumulative Gain.",
    )
    hit_rate: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Hit Rate — whether any relevant document was retrieved.",
    )
    context_precision: float = Field(default=0.0, ge=0.0, le=1.0)
    context_recall: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_similarity_score: float = Field(
        default=0.0, ge=0.0,
        description="Average similarity score of retrieved chunks.",
    )
    avg_retrieved_chunks: float = Field(
        default=0.0, ge=0.0,
        description="Average number of retrieved chunks.",
    )
    avg_retrieval_latency_ms: float = Field(
        default=0.0, ge=0.0,
        description="Average retrieval latency in milliseconds.",
    )


class GenerationMetricsResult(BaseModel):
    """Computed generation quality metrics for an evaluated sample."""

    model_config = ConfigDict(frozen=True)

    faithfulness: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Proportion of answer sentences grounded in context.",
    )
    answer_relevancy: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Keyword/concept overlap with expected answer and question.",
    )
    citation_coverage: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Proportion of answer sentences containing citation tags.",
    )
    citation_precision: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Proportion of cited sources that are valid context chunks.",
    )
    hallucination_rate: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="1.0 - faithfulness.",
    )
    context_utilization: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Proportion of provided chunks actually cited in the answer.",
    )
    answer_length: int = Field(
        default=0, ge=0,
        description="Character length of generated answer.",
    )
    word_count: int = Field(
        default=0, ge=0,
        description="Word count of generated answer.",
    )
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    llm_latency_ms: float = Field(
        default=0.0, ge=0.0,
        description="LLM generation latency in milliseconds.",
    )
    overall_response_time_ms: float = Field(
        default=0.0, ge=0.0,
        description="Total end-to-end response time in milliseconds.",
    )


class OverallMetrics(BaseModel):
    """Aggregate statistical metrics across a set of evaluation results."""

    model_config = ConfigDict(frozen=True)

    metric_name: str = Field(..., description="Name of the metric being aggregated.")
    mean: float = Field(default=0.0)
    std: float = Field(default=0.0)
    min_val: float = Field(default=0.0)
    max_val: float = Field(default=0.0)
    p50: float = Field(default=0.0, description="Median (50th percentile).")
    p90: float = Field(default=0.0, description="90th percentile.")
    p99: float = Field(default=0.0, description="99th percentile.")
    count: int = Field(default=0, ge=0)


class EvaluationConfiguration(BaseModel):
    """Configuration parameters for an evaluation run."""

    model_config = ConfigDict(frozen=True)

    k_values: list[int] = Field(
        default_factory=lambda: [1, 3, 5, 10, 20],
        description="K values for Recall@K and Precision@K computation.",
    )
    max_concurrency: int = Field(
        default=5, ge=1, le=100,
        description="Maximum concurrent evaluation tasks.",
    )
    timeout_seconds: float = Field(
        default=60.0, ge=1.0,
        description="Timeout per sample evaluation in seconds.",
    )
    providers: list[str] = Field(
        default_factory=lambda: ["mock"],
        description="LLM providers to evaluate.",
    )
    prompt_strategy: str = Field(
        default="standard_qa",
        description="Prompt strategy to use during evaluation.",
    )
    provider_override: str | None = Field(
        default=None,
        description="Single provider override for evaluation.",
    )
    model_override: str | None = Field(
        default=None,
        description="Model name override for evaluation.",
    )
    dataset_name: str = Field(
        default="default",
        description="Name identifier for the evaluation dataset.",
    )
    description: str = Field(
        default="",
        description="Human-readable description of this evaluation run.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional configuration metadata.",
    )


class EvaluationRawTrace(BaseModel):
    """Complete raw trace for a single evaluated question."""

    model_config = ConfigDict(frozen=False)

    question: str = Field(default="")
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    retrieved_chunk_texts: list[str] = Field(default_factory=list)
    retrieved_scores: list[float] = Field(default_factory=list)
    context_text: str = Field(default="")
    prompt_system: str = Field(default="")
    prompt_user: str = Field(default="")
    provider: str = Field(default="")
    model: str = Field(default="")
    generated_answer: str = Field(default="")
    extracted_citations: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_latency_ms: float = Field(default=0.0)
    context_build_latency_ms: float = Field(default=0.0)
    prompt_build_latency_ms: float = Field(default=0.0)
    llm_latency_ms: float = Field(default=0.0)
    citation_latency_ms: float = Field(default=0.0)
    total_latency_ms: float = Field(default=0.0)


class EvaluationResult(BaseModel):
    """Full evaluation result for a single benchmark sample."""

    model_config = ConfigDict(frozen=True)

    sample_id: str = Field(..., description="Identifier of the evaluated sample.")
    question: str = Field(..., description="Original evaluation question.")
    expected_answer: str = Field(default="")
    generated_answer: str = Field(default="")
    provider: str = Field(default="")
    model: str = Field(default="")
    prompt_strategy: str = Field(default="")
    retrieval_metrics: RetrievalMetricsResult = Field(
        default_factory=RetrievalMetricsResult,
    )
    generation_metrics: GenerationMetricsResult = Field(
        default_factory=GenerationMetricsResult,
    )
    citations_count: int = Field(default=0, ge=0)
    retrieved_chunks_count: int = Field(default=0, ge=0)
    used_chunks_count: int = Field(default=0, ge=0)
    success: bool = Field(default=True)
    error_message: str | None = Field(default=None)
    raw_trace: EvaluationRawTrace = Field(default_factory=EvaluationRawTrace)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationRunMetadata(BaseModel):
    """Metadata for an evaluation run."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique run identifier.",
    )
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
    completed_at: datetime | None = Field(default=None)
    provider: str = Field(default="")
    dataset_name: str = Field(default="default")
    total_samples: int = Field(default=0, ge=0)
    successful_samples: int = Field(default=0, ge=0)
    failed_samples: int = Field(default=0, ge=0)
    total_duration_seconds: float = Field(default=0.0, ge=0.0)
    configuration: EvaluationConfiguration = Field(
        default_factory=EvaluationConfiguration,
    )


class EvaluationReport(BaseModel):
    """Aggregate evaluation report for a dataset evaluation run."""

    model_config = ConfigDict(frozen=False)

    run_metadata: EvaluationRunMetadata = Field(
        default_factory=EvaluationRunMetadata,
    )
    results: list[EvaluationResult] = Field(
        default_factory=list,
        description="Individual sample evaluation results.",
    )
    overall_retrieval_metrics: list[OverallMetrics] = Field(
        default_factory=list,
    )
    overall_generation_metrics: list[OverallMetrics] = Field(
        default_factory=list,
    )
    configuration: EvaluationConfiguration = Field(
        default_factory=EvaluationConfiguration,
    )
    summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary statistics dictionary.",
    )


class ProviderBenchmark(BaseModel):
    """Aggregate benchmark result for a single LLM provider."""

    model_config = ConfigDict(frozen=True)

    provider_name: str = Field(...)
    model_name: str = Field(default="")
    total_samples: int = Field(default=0, ge=0)
    successful_samples: int = Field(default=0, ge=0)
    avg_latency_ms: float = Field(default=0.0, ge=0.0)
    avg_retrieval_score: float = Field(default=0.0, ge=0.0)
    avg_faithfulness: float = Field(default=0.0, ge=0.0)
    avg_hallucination_rate: float = Field(default=0.0, ge=0.0)
    avg_citation_coverage: float = Field(default=0.0, ge=0.0)
    avg_citation_precision: float = Field(default=0.0, ge=0.0)
    avg_answer_relevancy: float = Field(default=0.0, ge=0.0)
    avg_answer_length: float = Field(default=0.0, ge=0.0)
    avg_token_usage: float = Field(default=0.0, ge=0.0)
    avg_prompt_tokens: float = Field(default=0.0, ge=0.0)
    avg_completion_tokens: float = Field(default=0.0, ge=0.0)
    avg_context_utilization: float = Field(default=0.0, ge=0.0)
    avg_recall_at_5: float = Field(default=0.0, ge=0.0)
    avg_mrr: float = Field(default=0.0, ge=0.0)
    composite_score: float = Field(
        default=0.0, ge=0.0,
        description="Weighted composite quality score for ranking.",
    )
    report: EvaluationReport | None = Field(
        default=None,
        description="Underlying full evaluation report.",
    )


class BenchmarkResult(BaseModel):
    """Multi-provider comparative benchmark result with leaderboard."""

    model_config = ConfigDict(frozen=False)

    benchmark_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
    dataset_name: str = Field(default="default")
    total_samples: int = Field(default=0, ge=0)
    providers: list[ProviderBenchmark] = Field(
        default_factory=list,
        description="Per-provider benchmark results.",
    )
    leaderboard: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Ranked leaderboard of providers by composite score.",
    )
    configuration: EvaluationConfiguration = Field(
        default_factory=EvaluationConfiguration,
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )
