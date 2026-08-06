"""Enterprise RAG Evaluation, Benchmarking & Analytics Framework.

Public API for evaluation models, metrics calculators, dataset loading,
dataset building, evaluation engine, benchmarking, report generation,
export, notebook analytics, and evaluation history.
"""

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
from app.evaluation.history import (
    EvaluationHistory,
    TraceViewer,
    compare_runs,
)
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
    OverallMetrics,
    ProviderBenchmark,
    RetrievalMetricsResult,
)
from app.evaluation.reports import ReportGenerator

__all__ = [
    "BenchmarkResult",
    "DatasetBuilder",
    "DatasetLoader",
    "DifficultyLevel",
    "EvaluationConfiguration",
    "EvaluationDataFrameBuilder",
    "EvaluationDataset",
    "EvaluationExporter",
    "EvaluationHistory",
    "EvaluationRawTrace",
    "EvaluationReport",
    "EvaluationResult",
    "EvaluationRunMetadata",
    "EvaluationSample",
    "FailureAnalysisFrame",
    "GenerationMetricsCalculator",
    "GenerationMetricsFrame",
    "GenerationMetricsResult",
    "GroundTruthAnswer",
    "LeaderboardFrame",
    "OverallMetrics",
    "ProviderBenchmark",
    "ProviderComparisonFrame",
    "QuestionAnalysisFrame",
    "RAGBenchmark",
    "RAGEvaluator",
    "ReportGenerator",
    "RetrievalMetricsCalculator",
    "RetrievalMetricsFrame",
    "RetrievalMetricsResult",
    "TraceViewer",
    "compare_runs",
    "compute_overall_stats",
]
