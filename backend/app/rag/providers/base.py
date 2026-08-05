"""Abstract LLM Provider Interface and Provider Registry.

Defines the pluggable LLMProvider base class and dynamic LLMProviderRegistry
for decoupling generation pipelines from concrete model backends (Gemini, Ollama, OpenAI, Mock).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.rag.exceptions import ProviderNotFoundException
from app.rag.models import (
    FormattedPrompt,
    LLMGenerationOptions,
    LLMResponse,
    StreamChunk,
)


class LLMProvider(ABC):
    """Abstract interface defining an LLM inference backend."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique provider identifier (e.g. 'gemini', 'ollama', 'mock')."""
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model identifier used when not explicitly overridden."""
        ...

    @abstractmethod
    async def generate(
        self,
        prompt: FormattedPrompt,
        options: LLMGenerationOptions | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        """Execute full synchronous text generation against the LLM model.

        Args:
            prompt: Assembled prompt container with system and user turns.
            options: Runtime generation options (temperature, top_p, max_tokens).
            model: Optional runtime model override.

        Returns:
            LLMResponse: Standardized response with content, token usage, and latency.
        """
        ...

    @abstractmethod
    def stream_generate(
        self,
        prompt: FormattedPrompt,
        options: LLMGenerationOptions | None = None,
        model: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Execute streaming text generation emitting incremental text deltas.

        Args:
            prompt: Assembled prompt container.
            options: Runtime generation options.
            model: Optional model override.

        Yields:
            StreamChunk: Incremental token chunk.
        """
        ...

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Perform a lightweight health check probe against the provider backend."""
        ...

    async def close(self) -> None:
        """Release underlying network connections or resources."""
        return None


class LLMProviderRegistry:
    """Registry maintaining active LLM provider implementations."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def register(self, provider: LLMProvider) -> None:
        """Register an LLM provider backend."""
        self._providers[provider.name.lower().strip()] = provider

    def get(self, name: str) -> LLMProvider:
        """Get provider by name.

        Raises:
            ProviderNotFoundException: If provider is not registered.
        """
        norm_name = name.lower().strip()
        if norm_name not in self._providers:
            raise ProviderNotFoundException(provider_name=name)
        return self._providers[norm_name]

    def list_providers(self) -> list[str]:
        """Return list of all registered provider names."""
        return list(self._providers.keys())

    async def close_all(self) -> None:
        """Close all registered provider resources."""
        for provider in self._providers.values():
            await provider.close()
