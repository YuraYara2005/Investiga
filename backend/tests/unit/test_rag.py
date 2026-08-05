"""Comprehensive Unit and Integration Tests for the Enterprise RAG Generation Engine.

Covers ContextBuilder, PromptBuilder, Prompt Strategies, LLM Providers (Mock, Gemini, Ollama),
CitationExtractor, GuardrailPipeline, RAGOrchestrator, and RAGService.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.config import RAGSettings
from app.rag import (
    BuiltContext,
    CitationExtractor,
    ConciseStrategy,
    ContextBuilder,
    ContextSufficiencyGuardrail,
    ExecutiveSummaryStrategy,
    ExtractiveStrategy,
    FormattedPrompt,
    GeminiLLMProvider,
    GuardrailPipeline,
    HallucinationCitationGuardrail,
    InvestigativeAnalysisStrategy,
    LLMAuthenticationException,
    LLMMessage,
    LLMProviderException,
    LLMProviderRegistry,
    LLMTimeoutException,
    MessageRole,
    MockLLMProvider,
    OllamaLLMProvider,
    PromptBuilder,
    PromptStrategyNotFoundException,
    PromptStrategyRegistry,
    ProviderNotFoundException,
    QuerySafetyGuardrail,
    RAGOrchestrator,
    RAGRequest,
    RAGResponse,
    StandardQAStrategy,
    create_rag_service,
)
from app.retrieval.models import (
    RetrievalMetrics,
    RetrievalResult,
    RetrievalTrace,
    RetrievedChunk,
)
from app.retrieval.retriever import HybridRetriever


def _create_sample_chunk(
    chunk_id: str,
    doc_id: str,
    text: str,
    score: float,
    page: int = 1,
    heading: str = "Root Cause",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=doc_id,
        chunk_index=0,
        text=text,
        score=score,
        retrieval_sources=["dense", "bm25"],
        heading=heading,
        page_number=page,
        title="Postmortem Report",
        file_name="incident_report.pdf",
        category="security",
        tags=["incident", "database"],
        metadata={"author": "Incident Commander"},
    )


class TestContextBuilder:
    """Tests for ContextBuilder deduplication, budgeting, and rank preservation."""

    def test_context_builder_empty_chunks(self) -> None:
        builder = ContextBuilder(default_token_budget=1000)
        res = builder.build_context([])
        assert res.formatted_context == ""
        assert len(res.chunks) == 0
        assert res.total_tokens == 0
        assert res.dropped_chunks_count == 0

    def test_context_builder_deduplication_and_ranking(self) -> None:
        builder = ContextBuilder(default_token_budget=2000)
        c1 = _create_sample_chunk("c1", "d1", "Connection pool exhausted at 04:15 UTC.", 0.95)
        c2 = _create_sample_chunk("c2", "d1", "DB max_connections was set to 50.", 0.88)
        c1_dup = _create_sample_chunk("c1", "d1", "Duplicate chunk content.", 0.70)

        res = builder.build_context([c1, c2, c1_dup])
        assert len(res.chunks) == 2
        assert res.chunks[0].chunk_id == "c1"
        assert res.chunks[0].source_index == 1
        assert res.chunks[0].citation_tag == "[1]"
        assert res.chunks[1].chunk_id == "c2"
        assert res.chunks[1].source_index == 2
        assert "[1] Source [Document: Postmortem Report | Page: 1 | Section: Root Cause | Category: security]" in res.formatted_context
        assert "Connection pool exhausted" in res.formatted_context

    def test_context_builder_token_budget_and_truncation(self) -> None:
        # Strict low budget
        builder = ContextBuilder(default_token_budget=60, min_chunk_tokens=10)
        long_text = "Detailed forensic log statement " * 30
        c1 = _create_sample_chunk("c1", "d1", "Short message.", 0.95)
        c2 = _create_sample_chunk("c2", "d1", long_text, 0.90)
        c3 = _create_sample_chunk("c3", "d1", "Another message.", 0.80)

        res = builder.build_context([c1, c2, c3], token_budget=80)
        assert len(res.chunks) >= 1
        assert res.total_tokens <= 80
        assert res.dropped_chunks_count >= 1


class TestPromptStrategiesAndBuilder:
    """Tests for prompt strategies and PromptBuilder."""

    def test_standard_qa_strategy(self) -> None:
        strategy = StandardQAStrategy()
        sys = strategy.build_system_prompt("Insufficient info.")
        user = strategy.build_user_prompt("What failed?", "Context data")
        assert "Investiga AI" in sys
        assert "Insufficient info." in sys
        assert "Context data" in user
        assert "What failed?" in user

    def test_investigative_analysis_strategy(self) -> None:
        strategy = InvestigativeAnalysisStrategy()
        sys = strategy.build_system_prompt("No info.")
        user = strategy.build_user_prompt("Analyze breach", "Log dump")
        assert "Investiga Forensics AI" in sys
        assert "TIMELINE & SEQUENCE" in sys
        assert "Log dump" in user

    def test_executive_summary_strategy(self) -> None:
        strategy = ExecutiveSummaryStrategy()
        sys = strategy.build_system_prompt("No data.")
        assert "Investiga Executive Briefing AI" in sys
        assert "Key Findings" in sys

    def test_extractive_and_concise_strategies(self) -> None:
        extractive = ExtractiveStrategy()
        assert extractive.name == "extractive"
        assert "Fact Extractor" in extractive.build_system_prompt("N/A")

        concise = ConciseStrategy()
        assert concise.name == "concise"
        assert "Concise AI" in concise.build_system_prompt("N/A")

    def test_strategy_registry(self) -> None:
        registry = PromptStrategyRegistry()
        assert "standard_qa" in registry.list_strategies()
        assert "investigative_analysis" in registry.list_strategies()
        assert "executive_summary" in registry.list_strategies()

        s = registry.get("standard_qa")
        assert isinstance(s, StandardQAStrategy)

        with pytest.raises(PromptStrategyNotFoundException):
            registry.get("nonexistent_strategy")

    def test_prompt_builder_with_conversation_history(self) -> None:
        builder = PromptBuilder()
        context = BuiltContext(
            formatted_context="Sample context",
            chunks=[],
            total_tokens=10,
            token_budget=1000,
        )
        history = [
            LLMMessage(role=MessageRole.USER, content="Hello"),
            LLMMessage(role=MessageRole.ASSISTANT, content="Hi, how can I help?"),
        ]
        prompt = builder.build_prompt(
            query="Tell me about the outage.",
            context=context,
            strategy_name="standard_qa",
            conversation_history=history,
        )
        assert len(prompt.messages) == 4
        assert prompt.messages[0].role == MessageRole.SYSTEM
        assert prompt.messages[1].role == MessageRole.USER
        assert prompt.messages[2].role == MessageRole.ASSISTANT
        assert prompt.messages[3].role == MessageRole.USER
        assert prompt.estimated_prompt_tokens > 0


class TestCitationExtractor:
    """Tests for independent citation extraction."""

    def test_extract_single_and_multiple_citations(self) -> None:
        extractor = CitationExtractor()
        c1 = _create_sample_chunk("c1", "d1", "The primary server crashed.", 0.95)
        c2 = _create_sample_chunk("c2", "d2", "Memory leak in worker thread.", 0.85)

        context_chunk1 = ContextBuilder().build_context([c1, c2])

        text = "According to [1], the server crashed due to a leak [2]."
        citations = extractor.extract_citations(text, context_chunk1)

        assert len(citations) == 2
        assert citations[0].source_index == 1
        assert citations[0].chunk_id == "c1"
        assert citations[0].document_id == "d1"
        assert citations[1].source_index == 2
        assert citations[1].chunk_id == "c2"

    def test_extract_source_prefix_and_comma_citations(self) -> None:
        extractor = CitationExtractor()
        c1 = _create_sample_chunk("c1", "d1", "Database timeout.", 0.95)
        context = ContextBuilder().build_context([c1])

        text = "See [Source 1] for details."
        citations = extractor.extract_citations(text, context)
        assert len(citations) == 1
        assert citations[0].source_index == 1

    def test_extract_ignores_nonexistent_citation_indices(self) -> None:
        extractor = CitationExtractor()
        c1 = _create_sample_chunk("c1", "d1", "Database timeout.", 0.95)
        context = ContextBuilder().build_context([c1])

        text = "Claims from [99] and [1]."
        citations = extractor.extract_citations(text, context)
        assert len(citations) == 1
        assert citations[0].source_index == 1


class TestGuardrails:
    """Tests for pre and post generation guardrails."""

    @pytest.mark.asyncio
    async def test_context_sufficiency_guardrail(self) -> None:
        guard = ContextSufficiencyGuardrail()

        # 1. Empty chunks
        res_empty = await guard.evaluate(
            query="test", chunks=[], min_relevance_threshold=0.1
        )
        assert not res_empty.passed
        assert "No relevant knowledge chunks" in (res_empty.reason or "")

        # 2. Score below threshold
        low_chunk = _create_sample_chunk("c1", "d1", "Text", 0.05)
        res_low = await guard.evaluate(
            query="test", chunks=[low_chunk], min_relevance_threshold=0.1
        )
        assert not res_low.passed
        assert "below minimum relevance threshold" in (res_low.reason or "")

        # 3. Valid chunk
        high_chunk = _create_sample_chunk("c1", "d1", "Text", 0.85)
        res_high = await guard.evaluate(
            query="test", chunks=[high_chunk], min_relevance_threshold=0.1
        )
        assert res_high.passed

    @pytest.mark.asyncio
    async def test_query_safety_guardrail(self) -> None:
        guard = QuerySafetyGuardrail()
        res_short = await guard.evaluate(
            query="?", chunks=[], min_relevance_threshold=0.1
        )
        assert not res_short.passed

        res_ok = await guard.evaluate(
            query="What caused the incident?", chunks=[], min_relevance_threshold=0.1
        )
        assert res_ok.passed

    @pytest.mark.asyncio
    async def test_hallucination_citation_guardrail(self) -> None:
        guard = HallucinationCitationGuardrail()
        c1 = _create_sample_chunk("c1", "d1", "Text", 0.85)
        context = ContextBuilder().build_context([c1])

        # Valid citation [1]
        res_valid = await guard.evaluate(
            query="test",
            answer="Answer with [1].",
            citations=[],
            context=context,
        )
        assert res_valid.passed

        # Hallucinated citation [42]
        res_invalid = await guard.evaluate(
            query="test",
            answer="Answer with [42].",
            citations=[],
            context=context,
        )
        assert not res_invalid.passed
        assert "nonexistent sources" in (res_invalid.reason or "")

    @pytest.mark.asyncio
    async def test_guardrail_pipeline_aggregation(self) -> None:
        pipeline = GuardrailPipeline()
        c1 = _create_sample_chunk("c1", "d1", "Text", 0.85)
        context = ContextBuilder().build_context([c1])

        pre_res = await pipeline.run_pre_generation("Valid query?", [c1], 0.01)
        assert pre_res.is_safe
        assert not pre_res.fallback_used

        post_res = await pipeline.run_post_generation(
            query="Valid query?",
            answer="Answer citing [1]",
            citations=[],
            context=context,
            initial_result=pre_res,
        )
        assert post_res.is_safe


class TestLLMProviders:
    """Tests for LLMProvider implementations and registry."""

    @pytest.mark.asyncio
    async def test_mock_llm_provider_generate_and_stream(self) -> None:
        provider = MockLLMProvider(canned_response="Hello world [1]")
        prompt = FormattedPrompt(
            system_prompt="System",
            user_prompt="User",
            prompt_strategy="standard_qa",
            messages=[],
            estimated_prompt_tokens=5,
        )

        res = await provider.generate(prompt)
        assert res.content == "Hello world [1]"
        assert res.usage.prompt_tokens == 5
        assert res.usage.completion_tokens > 0

        # Test streaming
        chunks = []
        async for chunk in provider.stream_generate(prompt):
            chunks.append(chunk.content)
        assert "".join(chunks).strip() == "Hello world [1]"

    @pytest.mark.asyncio
    async def test_mock_llm_provider_failures(self) -> None:
        provider = MockLLMProvider(should_fail=True)
        prompt = FormattedPrompt(
            system_prompt="Sys", user_prompt="Usr", prompt_strategy="qa"
        )
        with pytest.raises(LLMProviderException):
            await provider.generate(prompt)

        provider.set_failure(False)
        provider.set_timeout(True)
        with pytest.raises(LLMTimeoutException):
            await provider.generate(prompt)

    @pytest.mark.asyncio
    async def test_gemini_provider_generate(self) -> None:
        mock_http_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "Gemini answer [1]"}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 25,
                "candidatesTokenCount": 10,
                "totalTokenCount": 35,
            },
        }
        mock_http_client.post.return_value = mock_response

        provider = GeminiLLMProvider(
            api_key="test-gemini-key",
            client=mock_http_client,
        )

        prompt = FormattedPrompt(
            system_prompt="System instructions",
            user_prompt="User inquiry",
            prompt_strategy="standard_qa",
            messages=[LLMMessage(role=MessageRole.USER, content="User inquiry")],
            estimated_prompt_tokens=25,
        )

        res = await provider.generate(prompt)
        assert res.content == "Gemini answer [1]"
        assert res.usage.prompt_tokens == 25
        assert res.usage.completion_tokens == 10
        assert res.model_name == "gemini-1.5-flash"

    @pytest.mark.asyncio
    async def test_gemini_provider_auth_error(self) -> None:
        mock_http_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_response.text = "API_KEY_INVALID"
        mock_http_client.post.return_value = mock_response

        provider = GeminiLLMProvider(
            api_key="bad-key",
            client=mock_http_client,
        )
        prompt = FormattedPrompt(
            system_prompt="Sys", user_prompt="Usr", prompt_strategy="qa"
        )
        with pytest.raises(LLMAuthenticationException):
            await provider.generate(prompt)

    @pytest.mark.asyncio
    async def test_ollama_provider_generate(self) -> None:
        mock_http_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Ollama answer [1]"},
            "prompt_eval_count": 30,
            "eval_count": 15,
            "done_reason": "stop",
        }
        mock_http_client.post.return_value = mock_response

        provider = OllamaLLMProvider(
            base_url="http://localhost:11434",
            default_model="llama3",
            client=mock_http_client,
        )
        prompt = FormattedPrompt(
            system_prompt="Sys",
            user_prompt="Usr",
            prompt_strategy="qa",
            messages=[LLMMessage(role=MessageRole.USER, content="Usr")],
        )
        res = await provider.generate(prompt)
        assert res.content == "Ollama answer [1]"
        assert res.usage.prompt_tokens == 30
        assert res.usage.completion_tokens == 15

    @pytest.mark.asyncio
    async def test_provider_registry(self) -> None:
        registry = LLMProviderRegistry()
        mock_p = MockLLMProvider()
        registry.register(mock_p)

        assert "mock" in registry.list_providers()
        assert registry.get("mock") is mock_p

        with pytest.raises(ProviderNotFoundException):
            registry.get("unknown_provider")

        await registry.close_all()


class TestRAGOrchestratorAndService:
    """Tests for the end-to-end RAGOrchestrator pipeline and RAGService facade."""

    @pytest.fixture
    def mock_retriever(self) -> AsyncMock:
        retriever = AsyncMock(spec=HybridRetriever)
        c1 = _create_sample_chunk("c1", "d1", "PostgreSQL max connections reached at 04:15 UTC.", 0.95)
        c2 = _create_sample_chunk("c2", "d1", "Connection leak in reporting service.", 0.85)

        retrieval_res = RetrievalResult(
            query="Why did the database crash?",
            normalized_query="why did the database crash",
            chunks=[c1, c2],
            total_retrieved=2,
            trace=RetrievalTrace(
                query="Why did the database crash?",
                normalized_query="why did the database crash",
                strategy="hybrid",
                latencies={"total_ms": 10.0},
            ),
            metrics=RetrievalMetrics(
                total_duration_ms=10.0,
                dense_candidates_count=1,
                sparse_candidates_count=1,
                fused_candidates_count=2,
            ),
        )
        retriever.search.return_value = retrieval_res
        return retriever

    @pytest.mark.asyncio
    async def test_orchestrator_query_happy_path(self, mock_retriever: AsyncMock) -> None:
        registry = LLMProviderRegistry()
        mock_provider = MockLLMProvider(
            canned_response="Based on [1], PostgreSQL reached max connections caused by [2]."
        )
        registry.register(mock_provider)

        orchestrator = RAGOrchestrator(
            retriever=mock_retriever,
            provider_registry=registry,
            settings=RAGSettings(llm_provider="mock"),
        )

        request = RAGRequest(
            query="Why did the database crash?",
            prompt_strategy="investigative_analysis",
        )

        response = await orchestrator.query(request)
        assert isinstance(response, RAGResponse)
        assert "max connections" in response.answer
        assert len(response.citations) == 2
        assert response.citations[0].source_index == 1
        assert response.citations[0].chunk_id == "c1"
        assert response.citations[1].source_index == 2
        assert response.citations[1].chunk_id == "c2"
        assert len(response.used_chunks) == 2
        assert response.metrics.total_duration_ms > 0
        assert response.trace.prompt_strategy == "investigative_analysis"
        assert response.provider == "mock"

    @pytest.mark.asyncio
    async def test_orchestrator_insufficient_context_fallback(self) -> None:
        empty_retriever = AsyncMock(spec=HybridRetriever)
        empty_retriever.search.return_value = RetrievalResult(
            query="Unknown topic",
            normalized_query="unknown topic",
            chunks=[],
            total_retrieved=0,
            trace=RetrievalTrace(
                query="Unknown topic",
                normalized_query="unknown topic",
                strategy="hybrid",
            ),
            metrics=RetrievalMetrics(),
        )
        registry = LLMProviderRegistry()
        mock_provider = MockLLMProvider()
        registry.register(mock_provider)

        orchestrator = RAGOrchestrator(
            retriever=empty_retriever,
            provider_registry=registry,
            settings=RAGSettings(llm_provider="mock", fallback_message="No info in knowledge base."),
        )

        response = await orchestrator.query(RAGRequest(query="Unknown topic"))
        assert response.answer == "No info in knowledge base."
        assert response.guardrail_result.fallback_used
        assert response.guardrail_result.insufficient_context
        assert mock_provider.call_count == 0  # LLM was never called!

    @pytest.mark.asyncio
    async def test_orchestrator_streaming_query(self, mock_retriever: AsyncMock) -> None:
        registry = LLMProviderRegistry()
        mock_provider = MockLLMProvider(canned_response="Streaming answer [1]")
        registry.register(mock_provider)

        orchestrator = RAGOrchestrator(
            retriever=mock_retriever,
            provider_registry=registry,
            settings=RAGSettings(llm_provider="mock"),
        )

        chunks = []
        async for chunk in orchestrator.stream_query(RAGRequest(query="Query")):
            chunks.append(chunk.content)

        assert "".join(chunks).strip() == "Streaming answer [1]"

    @pytest.mark.asyncio
    async def test_rag_service_facade(self, mock_retriever: AsyncMock) -> None:
        registry = LLMProviderRegistry()
        registry.register(MockLLMProvider(canned_response="Incident report summary [1]."))

        service = create_rag_service(
            retriever=mock_retriever,
            settings=RAGSettings(llm_provider="mock"),
            custom_registry=registry,
        )

        # 1. Ask standard
        res_ask = await service.ask("What happened?")
        assert res_ask.prompt_strategy == "standard_qa"
        assert len(res_ask.citations) == 1

        # 2. Ask investigation
        res_inv = await service.ask_investigation("Forensic breakdown")
        assert res_inv.prompt_strategy == "investigative_analysis"

        # 3. Ask executive summary
        res_exec = await service.ask_executive_summary("Executive brief")
        assert res_exec.prompt_strategy == "executive_summary"
