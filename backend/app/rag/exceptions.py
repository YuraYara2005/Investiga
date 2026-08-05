"""RAG Generation Engine Exception Hierarchy.

Defines all domain, provider, prompt, budget, and guardrail exceptions
used throughout the retrieval-augmented generation engine.
"""

from __future__ import annotations

from typing import Any

from app.exceptions.base import BaseAppException


class RAGException(BaseAppException):
    """Base exception for all RAG generation engine failures."""

    def __init__(
        self,
        message: str = "A RAG generation engine error occurred.",
        error_code: str = "RAG_ERROR",
        status_code: int | None = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            details=details,
        )


class InsufficientContextException(RAGException):
    """Raised when retrieved context is inadequate to answer the query."""

    def __init__(
        self,
        query: str,
        reason: str = "Insufficient relevant context found in knowledge base.",
        retrieved_count: int = 0,
        top_score: float = 0.0,
    ) -> None:
        super().__init__(
            message=f"Insufficient context for query '{query}': {reason}",
            details={
                "query": query,
                "reason": reason,
                "retrieved_count": retrieved_count,
                "top_score": top_score,
            },
        )
        self.error_code = "INSUFFICIENT_CONTEXT"


class LLMProviderException(RAGException):
    """Base exception for LLM provider errors."""

    def __init__(
        self,
        provider: str,
        message: str,
        model: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        det = details or {}
        det.update({"provider": provider, "model": model, "status_code": status_code})
        super().__init__(
            message=f"LLM Provider '{provider}' failed: {message}",
            error_code="LLM_PROVIDER_ERROR",
            status_code=status_code,
            details=det,
        )
        self.provider = provider
        self.model = model


class LLMTimeoutException(LLMProviderException):
    """Raised when an LLM provider request exceeds the timeout threshold."""

    def __init__(
        self,
        provider: str,
        timeout_seconds: float,
        model: str | None = None,
    ) -> None:
        super().__init__(
            provider=provider,
            model=model,
            message=f"Inference request timed out after {timeout_seconds}s.",
            details={"timeout_seconds": timeout_seconds},
        )
        self.error_code = "LLM_TIMEOUT"


class LLMRateLimitException(LLMProviderException):
    """Raised when an LLM provider returns 429 Too Many Requests."""

    def __init__(
        self,
        provider: str,
        retry_after: float | None = None,
        model: str | None = None,
    ) -> None:
        super().__init__(
            provider=provider,
            model=model,
            status_code=429,
            message="Rate limit exceeded (HTTP 429).",
            details={"retry_after": retry_after},
        )
        self.error_code = "LLM_RATE_LIMIT"


class LLMAuthenticationException(LLMProviderException):
    """Raised when provider credentials or API keys are invalid."""

    def __init__(
        self,
        provider: str,
        message: str = "Invalid API key or authentication failure.",
    ) -> None:
        super().__init__(
            provider=provider,
            status_code=401,
            message=message,
        )
        self.error_code = "LLM_AUTHENTICATION_ERROR"


class LLMInvalidResponseException(LLMProviderException):
    """Raised when provider returns an unparseable or empty response."""

    def __init__(
        self,
        provider: str,
        reason: str,
        raw_content: str | None = None,
    ) -> None:
        super().__init__(
            provider=provider,
            message=f"Invalid response payload: {reason}",
            details={"raw_content": raw_content},
        )
        self.error_code = "LLM_INVALID_RESPONSE"


class ContextBudgetExceededException(RAGException):
    """Raised when prompt and context exceed allowed token limits."""

    def __init__(
        self,
        total_tokens: int,
        max_budget: int,
    ) -> None:
        super().__init__(
            message=f"Context tokens ({total_tokens}) exceed budget ({max_budget}).",
            details={"total_tokens": total_tokens, "max_budget": max_budget},
        )
        self.error_code = "CONTEXT_BUDGET_EXCEEDED"


class PromptTemplateException(RAGException):
    """Raised when prompt template construction or formatting fails."""

    def __init__(
        self,
        strategy_name: str,
        reason: str,
    ) -> None:
        super().__init__(
            message=f"Prompt strategy '{strategy_name}' failed: {reason}",
            details={"strategy_name": strategy_name, "reason": reason},
        )
        self.error_code = "PROMPT_TEMPLATE_ERROR"


class GuardrailViolationException(RAGException):
    """Raised when strict guardrail evaluation fails and rejection is required."""

    def __init__(
        self,
        check_name: str,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        det = details or {}
        det.update({"check_name": check_name, "reason": reason})
        super().__init__(
            message=f"Guardrail check '{check_name}' failed: {reason}",
            details=det,
        )
        self.error_code = "GUARDRAIL_VIOLATION"


class ProviderNotFoundException(RAGException):
    """Raised when requested LLM provider backend is not registered."""

    def __init__(self, provider_name: str) -> None:
        super().__init__(
            message=f"LLM provider '{provider_name}' is not registered.",
            details={"provider_name": provider_name},
        )
        self.error_code = "PROVIDER_NOT_FOUND"


class PromptStrategyNotFoundException(RAGException):
    """Raised when requested prompt strategy is not registered."""

    def __init__(self, strategy_name: str) -> None:
        super().__init__(
            message=f"Prompt strategy '{strategy_name}' is not registered.",
            details={"strategy_name": strategy_name},
        )
        self.error_code = "PROMPT_STRATEGY_NOT_FOUND"
