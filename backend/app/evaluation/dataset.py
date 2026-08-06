"""Evaluation Dataset Loader and Container.

Supports loading benchmark evaluation datasets from JSON, JSONL, and CSV formats.
Provides an EvaluationDataset container with filtering, sampling, statistics,
and export capabilities.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.evaluation.models import EvaluationSample

logger = get_logger(__name__)


class DatasetLoader:
    """Static methods for loading EvaluationSample collections from various formats."""

    @staticmethod
    def load_json(source: str | Path) -> list[EvaluationSample]:
        """Load evaluation samples from a JSON file or JSON string.

        Expects a JSON array of objects with sample fields.

        Args:
            source: File path or JSON string.

        Returns:
            List of EvaluationSample objects.
        """
        if isinstance(source, Path):
            raw = source.read_text(encoding="utf-8")
        elif isinstance(source, str) and not source.strip().startswith("[") and Path(source).exists():
            raw = Path(source).read_text(encoding="utf-8")
        else:
            raw = str(source)

        data = json.loads(raw)
        if not isinstance(data, list):
            data = [data]

        samples = []
        for item in data:
            samples.append(_dict_to_sample(item))

        logger.info("dataset_loaded", format="json", sample_count=len(samples))
        return samples

    @staticmethod
    def load_jsonl(source: str | Path) -> list[EvaluationSample]:
        """Load evaluation samples from a JSONL file or JSONL string.

        Each line is a JSON object representing one sample.

        Args:
            source: File path or JSONL string.

        Returns:
            List of EvaluationSample objects.
        """
        if isinstance(source, Path):
            lines = source.read_text(encoding="utf-8").strip().splitlines()
        elif (
            isinstance(source, str)
            and "\n" not in source.strip()
            and not source.strip().startswith("{")
            and Path(source).exists()
        ):
            lines = Path(source).read_text(encoding="utf-8").strip().splitlines()
        else:
            lines = str(source).strip().splitlines()

        samples = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            samples.append(_dict_to_sample(item))

        logger.info("dataset_loaded", format="jsonl", sample_count=len(samples))
        return samples

    @staticmethod
    def load_csv(source: str | Path) -> list[EvaluationSample]:
        """Load evaluation samples from a CSV file or CSV string.

        Expected columns: question, expected_answer, expected_documents,
        expected_keywords, difficulty, category.

        List-type columns should be pipe-delimited (e.g., "doc1|doc2").

        Args:
            source: File path or CSV string.

        Returns:
            List of EvaluationSample objects.
        """
        if isinstance(source, Path):
            text = Path(source).read_text(encoding="utf-8")
        elif isinstance(source, str) and Path(source).exists():
            text = Path(source).read_text(encoding="utf-8")
        else:
            text = source

        reader = csv.DictReader(io.StringIO(text))
        samples = []
        for row in reader:
            sample_dict: dict[str, Any] = {
                "question": row.get("question", ""),
            }
            if "expected_answer" in row:
                sample_dict["expected_answer"] = row["expected_answer"]
            if row.get("expected_documents"):
                sample_dict["expected_documents"] = row["expected_documents"].split("|")
            if row.get("expected_keywords"):
                sample_dict["expected_keywords"] = row["expected_keywords"].split("|")
            if row.get("difficulty"):
                sample_dict["difficulty"] = row["difficulty"]
            if row.get("category"):
                sample_dict["category"] = row["category"]
            if row.get("id"):
                sample_dict["id"] = row["id"]

            samples.append(EvaluationSample(**sample_dict))

        logger.info("dataset_loaded", format="csv", sample_count=len(samples))
        return samples


class EvaluationDataset:
    """Container for evaluation dataset with filtering, sampling, and export.

    Args:
        samples: List of evaluation samples.
        name: Dataset name identifier.
    """

    def __init__(
        self,
        samples: list[EvaluationSample],
        name: str = "default",
    ) -> None:
        self._samples = list(samples)
        self._name = name

    @property
    def name(self) -> str:
        """Dataset name identifier."""
        return self._name

    @property
    def samples(self) -> list[EvaluationSample]:
        """All samples in the dataset."""
        return list(self._samples)

    def __len__(self) -> int:
        return len(self._samples)

    def __getitem__(self, index: int) -> EvaluationSample:
        return self._samples[index]

    def filter_by_category(self, category: str) -> EvaluationDataset:
        """Return a new dataset containing only samples in the given category.

        Args:
            category: Category string to filter by.

        Returns:
            Filtered EvaluationDataset.
        """
        filtered = [s for s in self._samples if s.category == category]
        return EvaluationDataset(filtered, name=f"{self._name}_{category}")

    def filter_by_difficulty(self, difficulty: str) -> EvaluationDataset:
        """Return a new dataset containing only samples with the given difficulty.

        Args:
            difficulty: Difficulty level to filter by.

        Returns:
            Filtered EvaluationDataset.
        """
        filtered = [s for s in self._samples if s.difficulty == difficulty]
        return EvaluationDataset(filtered, name=f"{self._name}_{difficulty}")

    def sample(self, n: int, seed: int | None = None) -> EvaluationDataset:
        """Return a random sample of n items from the dataset.

        Args:
            n: Number of samples to select.
            seed: Optional random seed for reproducibility.

        Returns:
            Sampled EvaluationDataset.
        """
        import random

        rng = random.Random(seed)
        count = min(n, len(self._samples))
        selected = rng.sample(self._samples, count)
        return EvaluationDataset(selected, name=f"{self._name}_sample_{n}")

    def statistics(self) -> dict[str, Any]:
        """Compute dataset statistics.

        Returns:
            Dictionary with total, category breakdown, difficulty breakdown.
        """
        categories: dict[str, int] = {}
        difficulties: dict[str, int] = {}
        for s in self._samples:
            categories[s.category] = categories.get(s.category, 0) + 1
            difficulties[s.difficulty] = difficulties.get(s.difficulty, 0) + 1
        return {
            "name": self._name,
            "total_samples": len(self._samples),
            "categories": categories,
            "difficulties": difficulties,
            "has_expected_answers": sum(1 for s in self._samples if s.expected_answer),
            "has_expected_documents": sum(
                1 for s in self._samples if s.expected_documents
            ),
        }

    def to_json(self, path: str | Path | None = None) -> str:
        """Export dataset as JSON string, optionally saving to file.

        Args:
            path: Optional output file path.

        Returns:
            JSON string representation.
        """
        data = [s.model_dump() for s in self._samples]
        json_str = json.dumps(data, indent=2, default=str)
        if path:
            Path(path).write_text(json_str, encoding="utf-8")
        return json_str

    def to_jsonl(self, path: str | Path | None = None) -> str:
        """Export dataset as JSONL string, optionally saving to file.

        Args:
            path: Optional output file path.

        Returns:
            JSONL string representation.
        """
        lines = [json.dumps(s.model_dump(), default=str) for s in self._samples]
        jsonl_str = "\n".join(lines)
        if path:
            Path(path).write_text(jsonl_str, encoding="utf-8")
        return jsonl_str

    def to_csv(self, path: str | Path | None = None) -> str:
        """Export dataset as CSV string, optionally saving to file.

        Args:
            path: Optional output file path.

        Returns:
            CSV string representation.
        """
        output = io.StringIO()
        fieldnames = [
            "id",
            "question",
            "expected_answer",
            "expected_documents",
            "expected_keywords",
            "difficulty",
            "category",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for s in self._samples:
            writer.writerow({
                "id": s.id,
                "question": s.question,
                "expected_answer": s.expected_answer,
                "expected_documents": "|".join(s.expected_documents),
                "expected_keywords": "|".join(s.expected_keywords),
                "difficulty": s.difficulty,
                "category": s.category,
            })
        csv_str = output.getvalue()
        if path:
            Path(path).write_text(csv_str, encoding="utf-8")
        return csv_str


def _dict_to_sample(data: dict[str, Any]) -> EvaluationSample:
    """Convert a dictionary to an EvaluationSample with flexible key handling.

    Args:
        data: Dictionary with sample fields.

    Returns:
        EvaluationSample instance.
    """
    # Normalize common key variations
    normalized: dict[str, Any] = {}
    normalized["question"] = data.get("question", data.get("query", ""))
    normalized["expected_answer"] = data.get(
        "expected_answer", data.get("answer", data.get("ground_truth", ""))
    )

    docs = data.get("expected_documents", data.get("relevant_documents", []))
    if isinstance(docs, str):
        docs = [d.strip() for d in docs.split("|") if d.strip()]
    normalized["expected_documents"] = docs

    keywords = data.get("expected_keywords", data.get("keywords", []))
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split("|") if k.strip()]
    normalized["expected_keywords"] = keywords

    if "difficulty" in data:
        normalized["difficulty"] = data["difficulty"]
    if "category" in data:
        normalized["category"] = data["category"]
    if "id" in data:
        normalized["id"] = str(data["id"])
    if "metadata" in data:
        normalized["metadata"] = data["metadata"]

    return EvaluationSample(**normalized)
