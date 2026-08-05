"""Prompt Strategy Pattern and Strategy Implementations.

Defines the pluggable PromptStrategy abstraction and concrete strategies for
Standard Q&A, Investigative Analysis, Executive Summary, Extractive, and Concise generation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.rag.exceptions import PromptStrategyNotFoundException


class PromptStrategy(ABC):
    """Abstract base class defining a prompt generation strategy."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique strategy name identifier."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable explanation of strategy behavior."""
        ...

    @abstractmethod
    def build_system_prompt(self, fallback_message: str) -> str:
        """Construct system persona, grounding constraints, and citation rules."""
        ...

    @abstractmethod
    def build_user_prompt(self, query: str, context: str) -> str:
        """Construct user turn combining contextual snippets and query."""
        ...


class StandardQAStrategy(PromptStrategy):
    """Balanced, objective enterprise Q&A strategy with strict citation grounding."""

    @property
    def name(self) -> str:
        return "standard_qa"

    @property
    def description(self) -> str:
        return "Balanced, objective question answering with grounded inline citations."

    def build_system_prompt(self, fallback_message: str) -> str:
        return (
            "You are Investiga AI, an enterprise incident investigation and knowledge assistant.\n"
            "Your objective is to provide accurate, truthful, and grounded answers strictly based on the provided Context.\n\n"
            "CORE OPERATING PRINCIPLES:\n"
            "1. GROUNDING: Base your answer ONLY on facts stated in the Context. Do NOT speculate, extrapolate, or assume facts not present.\n"
            "2. CITATIONS: Whenever stating a fact from a source snippet, cite it immediately using bracketed numeric citations such as [1], [2], etc.\n"
            "3. INSUFFICIENT CONTEXT: If the Context does NOT provide sufficient information to answer the query, reply with:\n"
            f"   \"{fallback_message}\"\n"
            "4. TONE: Maintain an objective, professional, and clear tone.\n"
        )

    def build_user_prompt(self, query: str, context: str) -> str:
        return (
            f"CONTEXT:\n"
            f"{context}\n\n"
            f"QUESTION:\n"
            f"{query}\n\n"
            f"ANSWER:"
        )


class InvestigativeAnalysisStrategy(PromptStrategy):
    """Forensic incident investigation, root cause analysis, and chronological timeline synthesis."""

    @property
    def name(self) -> str:
        return "investigative_analysis"

    @property
    def description(self) -> str:
        return "Deep forensic incident analysis, timeline sequencing, and root cause evidence correlation."

    def build_system_prompt(self, fallback_message: str) -> str:
        return (
            "You are Investiga Forensics AI, a specialized root cause analyst and incident investigator.\n"
            "Analyze the provided incident logs, reports, and evidence with rigorous scrutiny.\n\n"
            "ANALYSIS PROTOCOL:\n"
            "1. TIMELINE & SEQUENCE: Reconstruct chronological event sequences and causal links where available [1].\n"
            "2. ROOT CAUSE & ANOMALIES: Identify anomalous patterns, system failures, and configuration gaps directly supported by evidence.\n"
            "3. CITATIONS: Every analytical finding, timestamp, error code, and log reference MUST include the exact source citation (e.g. [1], [2]).\n"
            "4. EVIDENCE GAPS: Explicitly distinguish established facts from unresolved ambiguities.\n"
            "5. INSUFFICIENT CONTEXT: If the evidence is inadequate to perform analysis, reply with:\n"
            f"   \"{fallback_message}\"\n"
        )

    def build_user_prompt(self, query: str, context: str) -> str:
        return (
            f"INVESTIGATION EVIDENCE & LOGS:\n"
            f"{context}\n\n"
            f"INVESTIGATION INQUIRY:\n"
            f"{query}\n\n"
            f"STRUCTURED INVESTIGATIVE REPORT:"
        )


class ExecutiveSummaryStrategy(PromptStrategy):
    """High-level executive briefing with Key Findings, Incident Impact, and Recommendations."""

    @property
    def name(self) -> str:
        return "executive_summary"

    @property
    def description(self) -> str:
        return "High-level executive briefing summarizing key findings, impact, and action items."

    def build_system_prompt(self, fallback_message: str) -> str:
        return (
            "You are Investiga Executive Briefing AI.\n"
            "Provide concise, high-impact executive summaries for technical leaders and stakeholders.\n\n"
            "FORMAT REQUIREMENTS:\n"
            "- Executive Summary (2-3 sentences)\n"
            "- Key Findings (bulleted with citations [1], [2])\n"
            "- Incident Impact & Risk\n"
            "- Actionable Recommendations\n"
            "If the Context is insufficient, state:\n"
            f"\"{fallback_message}\"\n"
        )

    def build_user_prompt(self, query: str, context: str) -> str:
        return (
            f"CONTEXT:\n"
            f"{context}\n\n"
            f"TOPIC / INQUIRY:\n"
            f"{query}\n\n"
            f"EXECUTIVE BRIEFING:"
        )


class ExtractiveStrategy(PromptStrategy):
    """Strict factual extraction without synthesis, extrapolation, or interpretation."""

    @property
    def name(self) -> str:
        return "extractive"

    @property
    def description(self) -> str:
        return "Direct factual extraction without synthesis or paraphrasing."

    def build_system_prompt(self, fallback_message: str) -> str:
        return (
            "You are Investiga Fact Extractor.\n"
            "Extract ONLY direct facts, numbers, dates, and verbatim quotations relevant to the query from the Context.\n"
            "Do NOT extrapolate or synthesize new narratives.\n"
            "Every single point must include its source bracket citation [1].\n"
            f"If not found in context, return: \"{fallback_message}\"\n"
        )

    def build_user_prompt(self, query: str, context: str) -> str:
        return (
            f"SOURCE MATERIAL:\n"
            f"{context}\n\n"
            f"TARGET INFORMATION:\n"
            f"{query}\n\n"
            f"EXTRACTED FACTS:"
        )


class ConciseStrategy(PromptStrategy):
    """Direct, rapid-read bulleted answers with minimal overhead."""

    @property
    def name(self) -> str:
        return "concise"

    @property
    def description(self) -> str:
        return "Ultra-concise bulleted answers without conversational preamble."

    def build_system_prompt(self, fallback_message: str) -> str:
        return (
            "You are Investiga Concise AI.\n"
            "Provide direct, concise answers in bullet points. No preamble, no conversational pleasantries.\n"
            "Include inline source citations [1], [2].\n"
            f"If the answer is not in the context, output: \"{fallback_message}\"\n"
        )

    def build_user_prompt(self, query: str, context: str) -> str:
        return (
            f"CONTEXT:\n"
            f"{context}\n\n"
            f"QUESTION:\n"
            f"{query}\n\n"
            f"CONCISE ANSWER:"
        )


class PromptStrategyRegistry:
    """Registry maintaining active prompt generation strategies."""

    def __init__(self) -> None:
        self._strategies: dict[str, PromptStrategy] = {}
        # Register standard defaults
        self.register(StandardQAStrategy())
        self.register(InvestigativeAnalysisStrategy())
        self.register(ExecutiveSummaryStrategy())
        self.register(ExtractiveStrategy())
        self.register(ConciseStrategy())

    def register(self, strategy: PromptStrategy) -> None:
        """Register a new or custom prompt strategy."""
        self._strategies[strategy.name.lower().strip()] = strategy

    def get(self, name: str) -> PromptStrategy:
        """Lookup strategy by name.

        Raises:
            PromptStrategyNotFoundException: If strategy is not registered.
        """
        norm_name = name.lower().strip()
        if norm_name not in self._strategies:
            raise PromptStrategyNotFoundException(strategy_name=name)
        return self._strategies[norm_name]

    def list_strategies(self) -> list[str]:
        """Return all registered strategy names."""
        return list(self._strategies.keys())
