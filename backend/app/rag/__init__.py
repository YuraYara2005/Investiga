"""Enterprise RAG Generation Engine Package.

Exposes high-level domain models, services, orchestrators, prompt strategies,
guardrails, providers, and exceptions for incident retrieval-augmented generation.
"""

from app.rag.citations import CitationExtractor
from app.rag.context_builder import (
    ContextBuilder,
    ContextFormatter,
    DefaultContextFormatter,
    count_tokens,
)
from app.rag.exceptions import (
    ContextBudgetExceededException,
    GuardrailViolationException,
    InsufficientContextException,
    LLMAuthenticationException,
    LLMInvalidResponseException,
    LLMProviderException,
    LLMRateLimitException,
    LLMTimeoutException,
    PromptStrategyNotFoundException,
    PromptTemplateException,
    ProviderNotFoundException,
    RAGException,
)
from app.rag.guardrails import (
    ContextSufficiencyGuardrail,
    GuardrailPipeline,
    GuardrailStrategy,
    HallucinationCitationGuardrail,
    PostGenerationGuardrail,
    PreGenerationGuardrail,
    QuerySafetyGuardrail,
)
from app.rag.models import (
    BuiltContext,
    Citation,
    ContextChunk,
    FormattedPrompt,
    GuardrailCheck,
    GuardrailResult,
    LLMGenerationOptions,
    LLMMessage,
    LLMResponse,
    LLMUsage,
    MessageRole,
    RAGMetrics,
    RAGRequest,
    RAGResponse,
    RAGTrace,
    StreamChunk,
)
from app.rag.orchestrator import RAGOrchestrator
from app.rag.prompt_builder import PromptBuilder
from app.rag.prompt_strategies import (
    ConciseStrategy,
    ExecutiveSummaryStrategy,
    ExtractiveStrategy,
    InvestigativeAnalysisStrategy,
    PromptStrategy,
    PromptStrategyRegistry,
    StandardQAStrategy,
)
from app.rag.providers.base import LLMProvider, LLMProviderRegistry
from app.rag.providers.gemini import GeminiLLMProvider
from app.rag.providers.mock import MockLLMProvider
from app.rag.providers.ollama import OllamaLLMProvider
from app.rag.service import RAGService, create_rag_service

__all__ = [
    "BuiltContext",
    "Citation",
    "CitationExtractor",
    "ConciseStrategy",
    "ContextBudgetExceededException",
    "ContextBuilder",
    "ContextChunk",
    "ContextFormatter",
    "ContextSufficiencyGuardrail",
    "DefaultContextFormatter",
    "ExecutiveSummaryStrategy",
    "ExtractiveStrategy",
    "FormattedPrompt",
    "GeminiLLMProvider",
    "GuardrailCheck",
    "GuardrailPipeline",
    "GuardrailResult",
    "GuardrailStrategy",
    "GuardrailViolationException",
    "HallucinationCitationGuardrail",
    "InsufficientContextException",
    "InvestigativeAnalysisStrategy",
    "LLMAuthenticationException",
    "LLMGenerationOptions",
    "LLMInvalidResponseException",
    "LLMMessage",
    "LLMProvider",
    "LLMProviderException",
    "LLMProviderRegistry",
    "LLMRateLimitException",
    "LLMResponse",
    "LLMTimeoutException",
    "LLMUsage",
    "MessageRole",
    "MockLLMProvider",
    "OllamaLLMProvider",
    "PostGenerationGuardrail",
    "PreGenerationGuardrail",
    "PromptBuilder",
    "PromptStrategy",
    "PromptStrategyNotFoundException",
    "PromptStrategyRegistry",
    "PromptTemplateException",
    "ProviderNotFoundException",
    "QuerySafetyGuardrail",
    "RAGException",
    "RAGMetrics",
    "RAGOrchestrator",
    "RAGRequest",
    "RAGResponse",
    "RAGService",
    "RAGTrace",
    "StandardQAStrategy",
    "StreamChunk",
    "count_tokens",
    "create_rag_service",
]
