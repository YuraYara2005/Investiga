"""Retrieval and Generation Metrics Calculators for RAG Evaluation.

Implements mathematically correct IR metrics (Recall@K, Precision@K, MRR, MAP, nDCG,
Hit Rate, Context Precision/Recall) and generation quality metrics (Faithfulness,
Answer Relevancy, Citation Coverage/Precision, Hallucination Rate, Context Utilization).

All computations are purely algorithmic — no LLM-as-judge calls.
"""

from __future__ import annotations

import math
import re
from typing import Any

from app.core.logging import get_logger
from app.evaluation.models import (
    GenerationMetricsResult,
    RetrievalMetricsResult,
)

logger = get_logger(__name__)


class RetrievalMetricsCalculator:
    """Stateless calculator for retrieval quality metrics."""

    @staticmethod
    def recall_at_k(
        retrieved_ids: list[str],
        relevant_ids: list[str],
        k: int,
    ) -> float:
        """Compute Recall@K: fraction of relevant documents retrieved in top-K.

        Args:
            retrieved_ids: Ordered list of retrieved document/chunk IDs.
            relevant_ids: Set of ground-truth relevant document/chunk IDs.
            k: Cutoff rank.

        Returns:
            Recall@K score in [0.0, 1.0].
        """
        if not relevant_ids:
            return 1.0  # No relevant docs means trivially correct
        relevant_set = set(relevant_ids)
        top_k = retrieved_ids[:k]
        hits = sum(1 for doc_id in top_k if doc_id in relevant_set)
        return hits / len(relevant_set)

    @staticmethod
    def precision_at_k(
        retrieved_ids: list[str],
        relevant_ids: list[str],
        k: int,
    ) -> float:
        """Compute Precision@K: fraction of top-K results that are relevant.

        Args:
            retrieved_ids: Ordered list of retrieved document/chunk IDs.
            relevant_ids: Set of ground-truth relevant document/chunk IDs.
            k: Cutoff rank.

        Returns:
            Precision@K score in [0.0, 1.0].
        """
        if k <= 0:
            return 0.0
        relevant_set = set(relevant_ids)
        top_k = retrieved_ids[:k]
        if not top_k:
            return 0.0
        hits = sum(1 for doc_id in top_k if doc_id in relevant_set)
        return hits / len(top_k)

    @staticmethod
    def mrr(
        retrieved_ids: list[str],
        relevant_ids: list[str],
    ) -> float:
        """Compute Mean Reciprocal Rank (MRR).

        Returns the reciprocal of the rank of the first relevant document.

        Args:
            retrieved_ids: Ordered list of retrieved IDs.
            relevant_ids: Ground-truth relevant IDs.

        Returns:
            MRR score in [0.0, 1.0].
        """
        relevant_set = set(relevant_ids)
        for rank, doc_id in enumerate(retrieved_ids, start=1):
            if doc_id in relevant_set:
                return 1.0 / rank
        return 0.0

    @staticmethod
    def average_precision(
        retrieved_ids: list[str],
        relevant_ids: list[str],
    ) -> float:
        """Compute Average Precision (AP) for a single query.

        AP = (1/|R|) * sum_{k=1}^{n} P(k) * rel(k)

        where P(k) is Precision@k and rel(k) is 1 if doc at rank k is relevant.

        Args:
            retrieved_ids: Ordered list of retrieved IDs.
            relevant_ids: Ground-truth relevant IDs.

        Returns:
            Average Precision in [0.0, 1.0].
        """
        if not relevant_ids:
            return 1.0
        relevant_set = set(relevant_ids)
        cumulative_hits = 0
        precision_sum = 0.0
        for rank, doc_id in enumerate(retrieved_ids, start=1):
            if doc_id in relevant_set:
                cumulative_hits += 1
                precision_sum += cumulative_hits / rank
        return precision_sum / len(relevant_set)

    @staticmethod
    def ndcg_at_k(
        retrieved_ids: list[str],
        relevant_ids: list[str],
        k: int,
    ) -> float:
        """Compute Normalized Discounted Cumulative Gain (nDCG@K).

        Uses binary relevance (1 if relevant, 0 otherwise).

        DCG@K = sum_{i=1}^{K} rel(i) / log2(i + 1)
        IDCG@K = sum_{i=1}^{min(K, |R|)} 1 / log2(i + 1)
        nDCG = DCG / IDCG

        Args:
            retrieved_ids: Ordered list of retrieved IDs.
            relevant_ids: Ground-truth relevant IDs.
            k: Cutoff rank.

        Returns:
            nDCG@K score in [0.0, 1.0].
        """
        if not relevant_ids:
            return 1.0
        relevant_set = set(relevant_ids)
        top_k = retrieved_ids[:k]

        # DCG
        dcg = 0.0
        for i, doc_id in enumerate(top_k, start=1):
            if doc_id in relevant_set:
                dcg += 1.0 / math.log2(i + 1)

        # Ideal DCG
        ideal_count = min(k, len(relevant_set))
        idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_count + 1))

        if idcg == 0.0:
            return 0.0
        return dcg / idcg

    @staticmethod
    def hit_rate_at_k(
        retrieved_ids: list[str],
        relevant_ids: list[str],
        k: int,
    ) -> float:
        """Compute Hit Rate@K: 1.0 if any relevant doc in top-K, else 0.0.

        Args:
            retrieved_ids: Ordered list of retrieved IDs.
            relevant_ids: Ground-truth relevant IDs.
            k: Cutoff rank.

        Returns:
            1.0 or 0.0.
        """
        relevant_set = set(relevant_ids)
        top_k = retrieved_ids[:k]
        return 1.0 if any(doc_id in relevant_set for doc_id in top_k) else 0.0

    @staticmethod
    def context_precision(
        retrieved_ids: list[str],
        relevant_ids: list[str],
    ) -> float:
        """Context Precision: fraction of retrieved chunks that are relevant.

        Equivalent to Precision over the full retrieved set.

        Args:
            retrieved_ids: All retrieved IDs.
            relevant_ids: Ground-truth relevant IDs.

        Returns:
            Context Precision in [0.0, 1.0].
        """
        if not retrieved_ids:
            return 0.0
        relevant_set = set(relevant_ids)
        hits = sum(1 for doc_id in retrieved_ids if doc_id in relevant_set)
        return hits / len(retrieved_ids)

    @staticmethod
    def context_recall(
        retrieved_ids: list[str],
        relevant_ids: list[str],
    ) -> float:
        """Context Recall: fraction of relevant docs that appear in retrieved set.

        Equivalent to Recall over the full retrieved set.

        Args:
            retrieved_ids: All retrieved IDs.
            relevant_ids: Ground-truth relevant IDs.

        Returns:
            Context Recall in [0.0, 1.0].
        """
        if not relevant_ids:
            return 1.0
        relevant_set = set(relevant_ids)
        retrieved_set = set(retrieved_ids)
        hits = sum(1 for doc_id in relevant_set if doc_id in retrieved_set)
        return hits / len(relevant_set)

    @classmethod
    def compute_all(
        cls,
        retrieved_ids: list[str],
        relevant_ids: list[str],
        scores: list[float] | None = None,
        retrieval_latency_ms: float = 0.0,
        k_values: list[int] | None = None,
    ) -> RetrievalMetricsResult:
        """Compute all retrieval metrics.

        Args:
            retrieved_ids: Ordered list of retrieved document/chunk IDs.
            relevant_ids: Ground-truth relevant IDs.
            scores: Similarity scores corresponding to retrieved_ids.
            retrieval_latency_ms: Retrieval latency in milliseconds.
            k_values: K values for Recall@K. Defaults to [1, 3, 5, 10, 20].

        Returns:
            RetrievalMetricsResult with all computed metrics.
        """
        if k_values is None:
            k_values = [1, 3, 5, 10, 20]

        avg_score = 0.0
        if scores:
            avg_score = sum(scores) / len(scores)

        # Compute recall at standard K values
        recall_values: dict[int, float] = {}
        for k in [1, 3, 5, 10, 20]:
            recall_values[k] = cls.recall_at_k(retrieved_ids, relevant_ids, k)

        # Use max K for precision
        default_k = max(k_values) if k_values else 20
        precision = cls.precision_at_k(retrieved_ids, relevant_ids, default_k)

        return RetrievalMetricsResult(
            recall_at_1=round(recall_values.get(1, 0.0), 4),
            recall_at_3=round(recall_values.get(3, 0.0), 4),
            recall_at_5=round(recall_values.get(5, 0.0), 4),
            recall_at_10=round(recall_values.get(10, 0.0), 4),
            recall_at_20=round(recall_values.get(20, 0.0), 4),
            precision_at_k=round(precision, 4),
            mrr=round(cls.mrr(retrieved_ids, relevant_ids), 4),
            map_score=round(cls.average_precision(retrieved_ids, relevant_ids), 4),
            ndcg=round(cls.ndcg_at_k(retrieved_ids, relevant_ids, default_k), 4),
            hit_rate=round(cls.hit_rate_at_k(retrieved_ids, relevant_ids, default_k), 4),
            context_precision=round(cls.context_precision(retrieved_ids, relevant_ids), 4),
            context_recall=round(cls.context_recall(retrieved_ids, relevant_ids), 4),
            avg_similarity_score=round(avg_score, 4),
            avg_retrieved_chunks=float(len(retrieved_ids)),
            avg_retrieval_latency_ms=round(retrieval_latency_ms, 2),
        )


class GenerationMetricsCalculator:
    """Stateless calculator for generation quality metrics."""

    # Pattern for splitting text into sentences
    _SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

    # Pattern for citation tags in text: [1], [2], [Source 1], etc.
    _CITATION_PATTERN = re.compile(r"\[(?:Source\s*)?(\d+(?:\s*,\s*\d+)*)\]", re.IGNORECASE)

    @classmethod
    def faithfulness(
        cls,
        answer: str,
        context_texts: list[str],
    ) -> float:
        """Compute faithfulness: proportion of answer sentences grounded in context.

        A sentence is considered grounded if at least one significant word (4+ chars)
        from the sentence appears in the concatenated context text.

        Args:
            answer: Generated answer text.
            context_texts: List of context chunk texts.

        Returns:
            Faithfulness score in [0.0, 1.0].
        """
        if not answer.strip():
            return 0.0
        if not context_texts:
            return 0.0

        sentences = cls._split_sentences(answer)
        if not sentences:
            return 0.0

        # Build lowercased context corpus
        context_corpus = " ".join(t.lower() for t in context_texts)

        grounded_count = 0
        for sentence in sentences:
            words = sentence.lower().split()
            # A sentence is grounded if significant words overlap with context
            significant_words = [w for w in words if len(w) >= 4 and w.isalpha()]
            if not significant_words:
                grounded_count += 1  # Short/trivial sentences are assumed grounded
                continue
            overlap = sum(1 for w in significant_words if w in context_corpus)
            if overlap / len(significant_words) >= 0.3:
                grounded_count += 1

        return grounded_count / len(sentences)

    @classmethod
    def answer_relevancy(
        cls,
        answer: str,
        question: str,
        expected_keywords: list[str] | None = None,
    ) -> float:
        """Compute answer relevancy via keyword/concept overlap.

        Measures how relevant the answer is to the question and expected keywords.

        Args:
            answer: Generated answer text.
            question: Original evaluation question.
            expected_keywords: Optional expected keywords.

        Returns:
            Relevancy score in [0.0, 1.0].
        """
        if not answer.strip():
            return 0.0

        answer_lower = answer.lower()
        score_parts: list[float] = []

        # Question term overlap
        question_words = {
            w for w in question.lower().split()
            if len(w) >= 4 and w.isalpha()
        }
        if question_words:
            q_overlap = sum(1 for w in question_words if w in answer_lower)
            score_parts.append(min(1.0, q_overlap / max(len(question_words), 1)))

        # Expected keyword coverage
        if expected_keywords:
            kw_hits = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
            score_parts.append(kw_hits / len(expected_keywords))

        if not score_parts:
            return 0.5  # Neutral when no evaluation criteria available

        return sum(score_parts) / len(score_parts)

    @classmethod
    def citation_coverage(cls, answer: str) -> float:
        """Compute citation coverage: proportion of sentences with citation tags.

        Args:
            answer: Generated answer text.

        Returns:
            Citation coverage in [0.0, 1.0].
        """
        if not answer.strip():
            return 0.0

        sentences = cls._split_sentences(answer)
        if not sentences:
            return 0.0

        cited_count = sum(
            1 for s in sentences if cls._CITATION_PATTERN.search(s)
        )
        return cited_count / len(sentences)

    @classmethod
    def citation_precision(
        cls,
        answer: str,
        valid_source_indices: set[int],
    ) -> float:
        """Compute citation precision: fraction of cited indices that are valid.

        Args:
            answer: Generated answer text.
            valid_source_indices: Set of valid context chunk source indices.

        Returns:
            Citation precision in [0.0, 1.0].
        """
        cited_indices = cls._extract_citation_indices(answer)
        if not cited_indices:
            return 0.0

        valid_count = sum(1 for idx in cited_indices if idx in valid_source_indices)
        return valid_count / len(cited_indices)

    @staticmethod
    def hallucination_rate(faithfulness_score: float) -> float:
        """Compute hallucination rate: 1.0 - faithfulness.

        Args:
            faithfulness_score: Computed faithfulness score.

        Returns:
            Hallucination rate in [0.0, 1.0].
        """
        return max(0.0, min(1.0, 1.0 - faithfulness_score))

    @staticmethod
    def context_utilization(
        cited_chunk_indices: set[int],
        total_chunks: int,
    ) -> float:
        """Compute context utilization: fraction of provided chunks actually cited.

        Args:
            cited_chunk_indices: Set of chunk source indices cited in the answer.
            total_chunks: Total number of context chunks provided to the LLM.

        Returns:
            Utilization ratio in [0.0, 1.0].
        """
        if total_chunks <= 0:
            return 0.0
        return min(1.0, len(cited_chunk_indices) / total_chunks)

    @classmethod
    def compute_all(
        cls,
        answer: str,
        question: str,
        context_texts: list[str],
        valid_source_indices: set[int],
        total_context_chunks: int,
        expected_keywords: list[str] | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        llm_latency_ms: float = 0.0,
        overall_response_time_ms: float = 0.0,
    ) -> GenerationMetricsResult:
        """Compute all generation metrics.

        Args:
            answer: Generated answer text.
            question: Original question.
            context_texts: Context chunk texts.
            valid_source_indices: Set of valid citation source indices.
            total_context_chunks: Total context chunks provided.
            expected_keywords: Optional expected keywords.
            prompt_tokens: Prompt token count.
            completion_tokens: Completion token count.
            total_tokens: Total token count.
            llm_latency_ms: LLM generation latency.
            overall_response_time_ms: Total end-to-end response time.

        Returns:
            GenerationMetricsResult with all computed metrics.
        """
        faith = cls.faithfulness(answer, context_texts)
        relevancy = cls.answer_relevancy(answer, question, expected_keywords)
        cov = cls.citation_coverage(answer)
        prec = cls.citation_precision(answer, valid_source_indices)
        halluc = cls.hallucination_rate(faith)
        cited_indices = cls._extract_citation_indices(answer)
        util = cls.context_utilization(cited_indices, total_context_chunks)

        words = answer.split()

        return GenerationMetricsResult(
            faithfulness=round(faith, 4),
            answer_relevancy=round(relevancy, 4),
            citation_coverage=round(cov, 4),
            citation_precision=round(prec, 4),
            hallucination_rate=round(halluc, 4),
            context_utilization=round(util, 4),
            answer_length=len(answer),
            word_count=len(words),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            llm_latency_ms=round(llm_latency_ms, 2),
            overall_response_time_ms=round(overall_response_time_ms, 2),
        )

    @classmethod
    def _split_sentences(cls, text: str) -> list[str]:
        """Split text into non-empty sentences."""
        raw = cls._SENTENCE_SPLIT.split(text.strip())
        return [s.strip() for s in raw if s.strip()]

    @classmethod
    def _extract_citation_indices(cls, text: str) -> set[int]:
        """Extract unique integer citation indices from text."""
        indices: set[int] = set()
        for match in cls._CITATION_PATTERN.finditer(text):
            raw_group = match.group(1)
            for part in raw_group.split(","):
                clean = part.strip()
                if clean.isdigit():
                    indices.add(int(clean))
        return indices


def compute_overall_stats(values: list[float], metric_name: str) -> dict[str, Any]:
    """Compute aggregate statistics for a list of metric values.

    Args:
        values: List of numeric values.
        metric_name: Name of the metric.

    Returns:
        Dictionary with mean, std, min, max, p50, p90, p99, count.
    """
    if not values:
        return {
            "metric_name": metric_name,
            "mean": 0.0,
            "std": 0.0,
            "min_val": 0.0,
            "max_val": 0.0,
            "p50": 0.0,
            "p90": 0.0,
            "p99": 0.0,
            "count": 0,
        }

    n = len(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(variance)
    sorted_vals = sorted(values)

    def percentile(pct: float) -> float:
        idx = (pct / 100.0) * (n - 1)
        lower = math.floor(idx)
        upper = min(lower + 1, n - 1)
        weight = idx - lower
        return sorted_vals[lower] * (1 - weight) + sorted_vals[upper] * weight

    return {
        "metric_name": metric_name,
        "mean": round(mean, 4),
        "std": round(std, 4),
        "min_val": round(sorted_vals[0], 4),
        "max_val": round(sorted_vals[-1], 4),
        "p50": round(percentile(50), 4),
        "p90": round(percentile(90), 4),
        "p99": round(percentile(99), 4),
        "count": n,
    }
