"""Prompt Builder for Assembling Multi-Strategy Prompts and Conversation Contexts.

Coordinates prompt strategy resolution, system instruction generation, user turn formatting,
and multi-turn dialogue history concatenation.
"""

from __future__ import annotations

from app.core.config import RAGSettings
from app.rag.context_builder import count_tokens
from app.rag.models import BuiltContext, FormattedPrompt, LLMMessage, MessageRole
from app.rag.prompt_strategies import PromptStrategyRegistry


class PromptBuilder:
    """Orchestrates prompt generation across pluggable strategies."""

    def __init__(
        self,
        strategy_registry: PromptStrategyRegistry | None = None,
        settings: RAGSettings | None = None,
    ) -> None:
        """Initialize PromptBuilder.

        Args:
            strategy_registry: Registry containing prompt strategy implementations.
            settings: RAG configuration settings.
        """
        self._registry = strategy_registry or PromptStrategyRegistry()
        self._settings = settings or RAGSettings()

    @property
    def registry(self) -> PromptStrategyRegistry:
        """Access prompt strategy registry."""
        return self._registry

    def build_prompt(
        self,
        query: str,
        context: BuiltContext,
        strategy_name: str | None = None,
        fallback_message: str | None = None,
        conversation_history: list[LLMMessage] | None = None,
    ) -> FormattedPrompt:
        """Construct the complete formatted prompt container.

        Args:
            query: User question or investigation prompt.
            context: Built context container with formatted text snippets.
            strategy_name: Prompt strategy name override (e.g. 'standard_qa', 'investigative_analysis').
            fallback_message: Fallback text override.
            conversation_history: Optional list of prior conversation turns.

        Returns:
            FormattedPrompt: Prompt object ready for LLM provider execution.
        """
        strat_key = strategy_name or self._settings.prompt_strategy
        strategy = self._registry.get(strat_key)

        fallback = fallback_message or self._settings.fallback_message

        system_text = strategy.build_system_prompt(fallback_message=fallback)
        user_text = strategy.build_user_prompt(
            query=query.strip(),
            context=context.formatted_context,
        )

        # Assemble full conversation messages
        messages: list[LLMMessage] = [
            LLMMessage(role=MessageRole.SYSTEM, content=system_text)
        ]

        if conversation_history:
            messages.extend(conversation_history)

        messages.append(LLMMessage(role=MessageRole.USER, content=user_text))

        # Estimate tokens
        combined_text = "\n".join(m.content for m in messages)
        estimated_tokens = count_tokens(combined_text)

        return FormattedPrompt(
            system_prompt=system_text,
            user_prompt=user_text,
            prompt_strategy=strategy.name,
            messages=messages,
            estimated_prompt_tokens=estimated_tokens,
        )
