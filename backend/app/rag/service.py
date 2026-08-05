"""RAG Application Service Facade and Dependency Injection Factory.

Provides a unified interface for API controllers, background workers, and multi-agent systems
to interact with the Enterprise RAG Generation Engine.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.core.config import RAGSettings, get_settings
from app.rag.citations import CitationExtractor
from app.rag.context_builder import ContextBuilder
from app.rag.guardrails import GuardrailPipeline
from app.rag.models import (
    LLMMessage,
    RAGRequest,
    RAGResponse,
    StreamChunk,
)
from app.rag.orchestrator import RAGOrchestrator
from app.rag.prompt_builder import PromptBuilder
from app.rag.providers.base import LLMProviderRegistry
from app.rag.providers.gemini import GeminiLLMProvider
from app.rag.providers.mock import MockLLMProvider
from app.rag.providers.ollama import OllamaLLMProvider
from app.retrieval.models import SearchFilters, SearchOptions
from app.retrieval.retriever import HybridRetriever


class RAGService:
    """Application service facade for the RAG Generation Engine."""

    def __init__(self, orchestrator: RAGOrchestrator) -> None:
        """Initialize RAGService.

        Args:
            orchestrator: RAG pipeline orchestrator instance.
        """
        self._orchestrator = orchestrator

    @property
    def orchestrator(self) -> RAGOrchestrator:
        """Access the underlying pipeline orchestrator."""
        return self._orchestrator

    async def query(self, request: RAGRequest) -> RAGResponse:
        """Execute full RAG generation pipeline from a structured request."""
        return await self._orchestrator.query(request)

    async def ask(
        self,
        query: str,
        filters: SearchFilters | None = None,
        provider: str | None = None,
        model: str | None = None,
        prompt_strategy: str = "standard_qa",
        conversation_history: list[LLMMessage] | None = None,
    ) -> RAGResponse:
        """Convenience method for standard question answering."""
        req = RAGRequest(
            query=query,
            filters=filters,
            provider=provider,
            model=model,
            prompt_strategy=prompt_strategy,
            conversation_history=conversation_history or [],
        )
        return await self._orchestrator.query(req)

    async def ask_investigation(
        self,
        query: str,
        filters: SearchFilters | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> RAGResponse:
        """Perform deep forensic incident analysis and root cause correlation."""
        req = RAGRequest(
            query=query,
            filters=filters,
            provider=provider,
            model=model,
            prompt_strategy="investigative_analysis",
            retrieval_options=SearchOptions(top_k=30),
        )
        return await self._orchestrator.query(req)

    async def ask_executive_summary(
        self,
        query: str,
        filters: SearchFilters | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> RAGResponse:
        """Generate high-level executive briefing with risk summary and recommendations."""
        req = RAGRequest(
            query=query,
            filters=filters,
            provider=provider,
            model=model,
            prompt_strategy="executive_summary",
        )
        return await self._orchestrator.query(req)

    async def stream_query(self, request: RAGRequest) -> AsyncIterator[StreamChunk]:
        """Stream generated response tokens for real-time SSE/WebSocket endpoints."""
        async for chunk in self._orchestrator.stream_query(request):
            yield chunk


def create_rag_service(
    retriever: HybridRetriever,
    settings: RAGSettings | None = None,
    custom_registry: LLMProviderRegistry | None = None,
) -> RAGService:
    """Factory helper creating a fully-wired RAGService instance.

    Args:
        retriever: Injected HybridRetriever.
        settings: Optional RAG configuration settings.
        custom_registry: Optional custom LLMProviderRegistry.

    Returns:
        RAGService: Configured RAG application service facade.
    """
    rag_settings = settings or get_settings().rag

    if custom_registry is not None:
        registry = custom_registry
    else:
        registry = LLMProviderRegistry()
        # Register standard providers
        registry.register(GeminiLLMProvider(settings=rag_settings))
        registry.register(OllamaLLMProvider(settings=rag_settings))
        registry.register(MockLLMProvider())

    context_builder = ContextBuilder(
        default_token_budget=rag_settings.context_token_budget
    )
    prompt_builder = PromptBuilder(settings=rag_settings)
    citation_extractor = CitationExtractor()
    guardrail_pipeline = GuardrailPipeline()

    orchestrator = RAGOrchestrator(
        retriever=retriever,
        provider_registry=registry,
        context_builder=context_builder,
        prompt_builder=prompt_builder,
        citation_extractor=citation_extractor,
        guardrail_pipeline=guardrail_pipeline,
        settings=rag_settings,
    )

    return RAGService(orchestrator=orchestrator)
