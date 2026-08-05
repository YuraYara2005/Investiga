"""Guardrail Strategy Pattern and Implementations.

Provides pluggable pre-generation and post-generation safety verification pipelines
including context sufficiency detection, hallucination checks, and safe fallback handling.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from app.core.logging import get_logger
from app.rag.models import BuiltContext, Citation, GuardrailCheck, GuardrailResult
from app.retrieval.models import RetrievedChunk

logger = get_logger(__name__)


class GuardrailStrategy(ABC):
    """Base interface for all guardrail verification strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique check identifier."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of safety criteria."""
        ...


class PreGenerationGuardrail(GuardrailStrategy):
    """Abstract guardrail executed prior to calling LLM provider."""

    @abstractmethod
    async def evaluate(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        min_relevance_threshold: float,
    ) -> GuardrailCheck:
        """Evaluate pre-generation context and query constraints."""
        ...


class PostGenerationGuardrail(GuardrailStrategy):
    """Abstract guardrail executed after LLM response generation."""

    @abstractmethod
    async def evaluate(
        self,
        query: str,
        answer: str,
        citations: list[Citation],
        context: BuiltContext,
    ) -> GuardrailCheck:
        """Evaluate generated text for hallucinations, grounding, and safety."""
        ...


class ContextSufficiencyGuardrail(PreGenerationGuardrail):
    """Evaluates whether retrieved knowledge is sufficient to answer query."""

    @property
    def name(self) -> str:
        return "context_sufficiency"

    @property
    def description(self) -> str:
        return "Ensures at least one retrieved chunk exists and meets the minimum relevance score threshold."

    async def evaluate(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        min_relevance_threshold: float,
    ) -> GuardrailCheck:
        if not chunks:
            return GuardrailCheck(
                check_name=self.name,
                passed=False,
                reason="No relevant knowledge chunks found for query.",
                details={"chunk_count": 0, "threshold": min_relevance_threshold},
            )

        top_score = max(c.score for c in chunks)
        if top_score < min_relevance_threshold:
            return GuardrailCheck(
                check_name=self.name,
                passed=False,
                reason=f"Top retrieval score ({top_score:.4f}) is below minimum relevance threshold ({min_relevance_threshold:.4f}).",
                details={"top_score": top_score, "threshold": min_relevance_threshold},
            )

        return GuardrailCheck(
            check_name=self.name,
            passed=True,
            reason=None,
            details={"chunk_count": len(chunks), "top_score": top_score},
        )


class QuerySafetyGuardrail(PreGenerationGuardrail):
    """Validates query structure and basic boundary constraints."""

    @property
    def name(self) -> str:
        return "query_safety"

    @property
    def description(self) -> str:
        return "Validates query length, character structure, and basic safety."

    async def evaluate(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        min_relevance_threshold: float,
    ) -> GuardrailCheck:
        clean_q = query.strip()
        if len(clean_q) < 2:
            return GuardrailCheck(
                check_name=self.name,
                passed=False,
                reason="Query is too short or empty.",
                details={"length": len(clean_q)},
            )

        return GuardrailCheck(
            check_name=self.name,
            passed=True,
            reason=None,
            details={"length": len(clean_q)},
        )


class HallucinationCitationGuardrail(PostGenerationGuardrail):
    """Verifies that numeric bracket citations in answer correspond to actual context chunks."""

    @property
    def name(self) -> str:
        return "citation_hallucination_check"

    @property
    def description(self) -> str:
        return "Detects fabricated or invalid bracket citations in generated responses."

    async def evaluate(
        self,
        query: str,
        answer: str,
        citations: list[Citation],
        context: BuiltContext,
    ) -> GuardrailCheck:
        valid_indices = {chunk.source_index for chunk in context.chunks}

        # Find all cited bracket numbers in text
        raw_citations = re.findall(r"\[(\d+)\]", answer)
        cited_indices = {int(c) for c in raw_citations}

        invalid_indices = cited_indices - valid_indices

        if invalid_indices:
            return GuardrailCheck(
                check_name=self.name,
                passed=False,
                reason=f"Generated answer cited nonexistent sources: {sorted(invalid_indices)}",
                details={
                    "invalid_indices": list(invalid_indices),
                    "valid_indices": list(valid_indices),
                },
            )

        return GuardrailCheck(
            check_name=self.name,
            passed=True,
            reason=None,
            details={"valid_citations_count": len(citations)},
        )


class GuardrailPipeline:
    """Executes pre and post guardrails in a configurable pipeline."""

    def __init__(
        self,
        pre_guardrails: list[PreGenerationGuardrail] | None = None,
        post_guardrails: list[PostGenerationGuardrail] | None = None,
    ) -> None:
        self._pre_guardrails = pre_guardrails or [
            QuerySafetyGuardrail(),
            ContextSufficiencyGuardrail(),
        ]
        self._post_guardrails = post_guardrails or [
            HallucinationCitationGuardrail(),
        ]

    def get_guardrail_names(self) -> list[str]:
        """Return all active guardrail check names."""
        names = [g.name for g in self._pre_guardrails]
        names.extend(g.name for g in self._post_guardrails)
        return names

    async def run_pre_generation(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        min_relevance_threshold: float,
    ) -> GuardrailResult:
        """Run all pre-generation guardrails."""
        checks: list[GuardrailCheck] = []
        is_safe = True
        insufficient_context = False
        failure_reasons: list[str] = []

        for guard in self._pre_guardrails:
            check = await guard.evaluate(
                query=query,
                chunks=chunks,
                min_relevance_threshold=min_relevance_threshold,
            )
            checks.append(check)
            if not check.passed:
                is_safe = False
                failure_reasons.append(f"{guard.name}: {check.reason}")
                if guard.name == "context_sufficiency":
                    insufficient_context = True

        return GuardrailResult(
            is_safe=is_safe,
            insufficient_context=insufficient_context,
            confidence_score=1.0 if is_safe else 0.0,
            checks=checks,
            fallback_used=not is_safe,
            fallback_reason="; ".join(failure_reasons) if failure_reasons else None,
        )

    async def run_post_generation(
        self,
        query: str,
        answer: str,
        citations: list[Citation],
        context: BuiltContext,
        initial_result: GuardrailResult,
    ) -> GuardrailResult:
        """Run all post-generation guardrails and merge results."""
        checks = list(initial_result.checks)
        is_safe = initial_result.is_safe
        failure_reasons: list[str] = []
        if initial_result.fallback_reason:
            failure_reasons.append(initial_result.fallback_reason)

        for guard in self._post_guardrails:
            check = await guard.evaluate(
                query=query,
                answer=answer,
                citations=citations,
                context=context,
            )
            checks.append(check)
            if not check.passed:
                is_safe = False
                failure_reasons.append(f"{guard.name}: {check.reason}")

        return GuardrailResult(
            is_safe=is_safe,
            insufficient_context=initial_result.insufficient_context,
            confidence_score=1.0 if is_safe else 0.5,
            checks=checks,
            fallback_used=initial_result.fallback_used or not is_safe,
            fallback_reason="; ".join(failure_reasons) if failure_reasons else None,
        )
