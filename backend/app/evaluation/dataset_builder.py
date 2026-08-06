"""Benchmark Dataset Builder from Knowledge Base.

Creates EvaluationSample objects from indexed KnowledgeDocument and KnowledgeChunk
entities, allowing Investiga to build its own benchmark corpus from uploaded
documentation rather than relying only on manually written datasets.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.core.logging import get_logger
from app.evaluation.dataset import EvaluationDataset
from app.evaluation.models import EvaluationSample

logger = get_logger(__name__)


class DatasetBuilder:
    """Builds benchmark evaluation datasets from knowledge base documents.

    Generates EvaluationSample objects by extracting questions from document
    metadata, chunk headings, and content. Supports manual editing and
    augmentation.
    """

    def __init__(self) -> None:
        self._samples: list[EvaluationSample] = []

    @property
    def samples(self) -> list[EvaluationSample]:
        """Current accumulated samples."""
        return list(self._samples)

    def add_sample(self, sample: EvaluationSample) -> None:
        """Add a manually created evaluation sample.

        Args:
            sample: EvaluationSample to add.
        """
        self._samples.append(sample)
        logger.debug("sample_added", sample_id=sample.id, question=sample.question[:80])

    def add_samples(self, samples: list[EvaluationSample]) -> None:
        """Add multiple evaluation samples.

        Args:
            samples: List of EvaluationSample objects to add.
        """
        self._samples.extend(samples)
        logger.debug("samples_added", count=len(samples))

    def create_sample(
        self,
        question: str,
        expected_answer: str = "",
        expected_documents: list[str] | None = None,
        expected_keywords: list[str] | None = None,
        difficulty: str = "medium",
        category: str = "general",
        metadata: dict[str, Any] | None = None,
    ) -> EvaluationSample:
        """Create and add a new evaluation sample.

        Args:
            question: Benchmark question.
            expected_answer: Expected/reference answer.
            expected_documents: Expected document IDs for retrieval.
            expected_keywords: Keywords expected in a correct answer.
            difficulty: Difficulty level (easy, medium, hard, expert).
            category: Question category/domain.
            metadata: Additional metadata.

        Returns:
            Created EvaluationSample.
        """
        sample = EvaluationSample(
            question=question,
            expected_answer=expected_answer,
            expected_documents=expected_documents or [],
            expected_keywords=expected_keywords or [],
            difficulty=difficulty,
            category=category,
            metadata=metadata or {},
        )
        self._samples.append(sample)
        return sample

    def from_document_metadata(
        self,
        document_id: str,
        title: str,
        category: str = "general",
        description: str = "",
        tags: list[str] | None = None,
        difficulty: str = "medium",
    ) -> list[EvaluationSample]:
        """Generate starter benchmark samples from document metadata.

        Creates questions about the document's purpose, content, and key topics
        based on title, description, and tags.

        Args:
            document_id: Document UUID string.
            title: Document title.
            category: Document category.
            description: Document description.
            tags: Document tags.
            difficulty: Default difficulty for generated samples.

        Returns:
            List of generated EvaluationSample objects.
        """
        generated: list[EvaluationSample] = []

        # Q1: What does this document cover?
        q1 = EvaluationSample(
            question=f"What does the document '{title}' cover?",
            expected_answer=description or f"Information from {title}",
            expected_documents=[document_id],
            expected_keywords=_extract_keywords_from_title(title),
            difficulty=difficulty,
            category=category,
            metadata={"source": "auto_generated", "document_id": document_id},
        )
        generated.append(q1)

        # Q2: Summarize document
        q2 = EvaluationSample(
            question=f"Summarize the key points from '{title}'.",
            expected_answer=description or "",
            expected_documents=[document_id],
            expected_keywords=_extract_keywords_from_title(title),
            difficulty=difficulty,
            category=category,
            metadata={"source": "auto_generated", "document_id": document_id},
        )
        generated.append(q2)

        # Q3: Tag-based question if tags available
        if tags:
            tag_text = ", ".join(tags[:5])
            q3 = EvaluationSample(
                question=f"What information is available about {tag_text}?",
                expected_answer="",
                expected_documents=[document_id],
                expected_keywords=tags[:5],
                difficulty=difficulty,
                category=category,
                metadata={"source": "auto_generated", "document_id": document_id},
            )
            generated.append(q3)

        self._samples.extend(generated)
        logger.info(
            "samples_generated_from_document",
            document_id=document_id,
            title=title,
            generated_count=len(generated),
        )
        return generated

    def from_chunks(
        self,
        document_id: str,
        chunks: list[dict[str, Any]],
        category: str = "general",
        difficulty: str = "medium",
        max_samples_per_doc: int = 10,
    ) -> list[EvaluationSample]:
        """Generate benchmark samples from document chunks.

        Creates questions from chunk headings and content.

        Args:
            document_id: Parent document ID.
            chunks: List of chunk dicts with 'text', 'heading', 'chunk_index' keys.
            category: Category for generated samples.
            difficulty: Difficulty level.
            max_samples_per_doc: Maximum samples to generate per document.

        Returns:
            List of generated EvaluationSample objects.
        """
        generated: list[EvaluationSample] = []

        for chunk in chunks[:max_samples_per_doc]:
            text = chunk.get("text", "")
            heading = chunk.get("heading", "")
            chunk_id = chunk.get("chunk_id", str(uuid.uuid4()))

            if not text.strip():
                continue

            # Create a question from heading or first sentence
            if heading:
                question = f"What information is provided about '{heading}'?"
            else:
                first_sentence = text.split(".")[0].strip()
                if len(first_sentence) > 20:
                    question = f"Explain: {first_sentence[:100]}?"
                else:
                    continue

            keywords = _extract_keywords_from_text(text)

            sample = EvaluationSample(
                question=question,
                expected_answer=text[:500],
                expected_documents=[document_id],
                expected_keywords=keywords[:10],
                difficulty=difficulty,
                category=category,
                metadata={
                    "source": "auto_generated",
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "heading": heading,
                },
            )
            generated.append(sample)

        self._samples.extend(generated)
        logger.info(
            "samples_generated_from_chunks",
            document_id=document_id,
            chunk_count=len(chunks),
            generated_count=len(generated),
        )
        return generated

    def build(self, name: str = "auto_generated") -> EvaluationDataset:
        """Build an EvaluationDataset from all accumulated samples.

        Args:
            name: Dataset name identifier.

        Returns:
            EvaluationDataset containing all samples.
        """
        logger.info("dataset_built", name=name, total_samples=len(self._samples))
        return EvaluationDataset(self._samples, name=name)

    def clear(self) -> None:
        """Remove all accumulated samples."""
        self._samples.clear()


def _extract_keywords_from_title(title: str) -> list[str]:
    """Extract significant keywords from a document title.

    Args:
        title: Document title string.

    Returns:
        List of significant words (4+ chars, alphabetic).
    """
    stop_words = {
        "the", "and", "for", "with", "from", "this", "that", "into",
        "about", "over", "after", "before", "between", "through",
        "during", "report", "document", "guide", "manual",
    }
    words = title.lower().split()
    return [
        w.strip(".,;:!?()-'\"")
        for w in words
        if len(w) >= 4 and w.isalpha() and w.lower() not in stop_words
    ]


def _extract_keywords_from_text(text: str, max_keywords: int = 10) -> list[str]:
    """Extract significant keywords from text based on word frequency.

    Args:
        text: Input text.
        max_keywords: Maximum keywords to return.

    Returns:
        List of significant keywords sorted by frequency.
    """
    stop_words = {
        "the", "and", "for", "with", "from", "this", "that", "into",
        "about", "over", "after", "before", "between", "through",
        "during", "have", "been", "were", "will", "would", "could",
        "should", "which", "their", "there", "then", "than", "also",
        "when", "what", "where", "more", "some", "each", "other",
    }
    words = text.lower().split()
    freq: dict[str, int] = {}
    for w in words:
        clean = w.strip(".,;:!?()-'\"")
        if len(clean) >= 4 and clean.isalpha() and clean not in stop_words:
            freq[clean] = freq.get(clean, 0) + 1

    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [w for w, _ in sorted_words[:max_keywords]]
