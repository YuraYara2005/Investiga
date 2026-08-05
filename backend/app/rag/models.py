"""RAG Generation Domain Models, DTOs, and Telemetry Structures.

Defines the contract for context chunks, prompt structures, multi-turn messages,
LLM options and responses, streaming chunks, citations, guardrails, and telemetry traces.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.retrieval.models import (
    RetrievalResult,
    SearchFilters,
    SearchOptions,
)


class MessageRole(StrEnum):
    """Role identifiers for multi-turn conversation messages."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class LLMMessage(BaseModel):
    """A single conversation message supporting multi-turn dialogues and agent tools."""

    model_config = ConfigDict(frozen=True)

    role: MessageRole = Field(
        default=MessageRole.USER,
        description="The entity sending the message.",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Text content of the message.",
    )
    name: str | None = Field(
        default=None,
        description="Optional author/function name.",
    )
    tool_call_id: str | None = Field(
        default=None,
        description="Identifier if this message is a tool response.",
    )


class ContextChunk(BaseModel):
    """Enriched document chunk formatted and placed into the LLM context window."""

    model_config = ConfigDict(frozen=True)

    source_index: int = Field(
        ...,
        ge=1,
        description="1-based ordinal citation index (e.g., 1 for [1]).",
    )
    citation_tag: str = Field(
        ...,
        description="Citation marker string (e.g., '[1]' or '[Source 1]').",
    )
    chunk_id: str = Field(
        ...,
        description="Unique identifier of the knowledge chunk.",
    )
    document_id: str = Field(
        ...,
        description="Unique identifier of the parent document.",
    )
    chunk_index: int = Field(
        default=0,
        description="Sequential index of chunk in original document.",
    )
    text: str = Field(
        ...,
        description="Sanitized text content included in the context.",
    )
    token_count: int = Field(
        ...,
        ge=0,
        description="Estimated or exact token count of this chunk.",
    )
    score: float = Field(
        ...,
        description="Retrieval relevance/fusion score.",
    )
    heading: str | None = Field(
        default=None,
        description="Section heading hierarchy.",
    )
    page_number: int | None = Field(
        default=None,
        description="Physical page number in source file.",
    )
    title: str | None = Field(
        default=None,
        description="Document title.",
    )
    file_name: str | None = Field(
        default=None,
        description="Source document file name.",
    )
    category: str | None = Field(
        default=None,
        description="Document category or domain.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Associated document tags.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional chunk metadata.",
    )


class BuiltContext(BaseModel):
    """Output from the ContextBuilder ready for prompt injection."""

    model_config = ConfigDict(frozen=True)

    formatted_context: str = Field(
        ...,
        description="Full formatted context text containing attributed snippets.",
    )
    chunks: list[ContextChunk] = Field(
        default_factory=list,
        description="Ordered list of context chunks included within budget.",
    )
    total_tokens: int = Field(
        default=0,
        ge=0,
        description="Total token consumption of the formatted context.",
    )
    token_budget: int = Field(
        default=4000,
        ge=1,
        description="Configured maximum token budget for context.",
    )
    truncated_chunks_count: int = Field(
        default=0,
        ge=0,
        description="Number of chunks whose text was adaptively truncated.",
    )
    dropped_chunks_count: int = Field(
        default=0,
        ge=0,
        description="Number of retrieved chunks omitted due to budget constraints.",
    )


class FormattedPrompt(BaseModel):
    """Complete assembled prompt container passed to the LLM Provider."""

    model_config = ConfigDict(frozen=True)

    system_prompt: str = Field(
        ...,
        description="System instruction defining persona, grounding rules, and citation format.",
    )
    user_prompt: str = Field(
        ...,
        description="User turn combining query, context snippets, and instructions.",
    )
    prompt_strategy: str = Field(
        default="standard_qa",
        description="Name of the prompt strategy applied.",
    )
    messages: list[LLMMessage] = Field(
        default_factory=list,
        description="Full conversation message sequence (including history).",
    )
    estimated_prompt_tokens: int = Field(
        default=0,
        ge=0,
        description="Estimated token count for prompt inputs.",
    )


class LLMGenerationOptions(BaseModel):
    """Runtime options for LLM text generation."""

    model_config = ConfigDict(frozen=True)

    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Sampling temperature.",
    )
    top_p: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling probability threshold.",
    )
    max_output_tokens: int = Field(
        default=2048,
        ge=1,
        description="Maximum generation token length.",
    )
    stop_sequences: list[str] = Field(
        default_factory=list,
        description="Optional stop sequences to halt generation.",
    )
    timeout_seconds: float = Field(
        default=30.0,
        ge=0.1,
        description="Maximum request timeout in seconds.",
    )


class LLMUsage(BaseModel):
    """Token consumption metrics for an LLM generation call."""

    model_config = ConfigDict(frozen=True)

    prompt_tokens: int = Field(
        default=0,
        ge=0,
        description="Number of input/prompt tokens processed.",
    )
    completion_tokens: int = Field(
        default=0,
        ge=0,
        description="Number of output tokens generated.",
    )
    total_tokens: int = Field(
        default=0,
        ge=0,
        description="Total tokens consumed.",
    )
    estimated: bool = Field(
        default=False,
        description="True if tokens were estimated locally rather than reported by provider.",
    )


class StreamChunk(BaseModel):
    """A streaming token/text delta emitted by an LLM provider."""

    model_config = ConfigDict(frozen=True)

    content: str = Field(
        default="",
        description="Incremental text delta.",
    )
    finish_reason: str | None = Field(
        default=None,
        description="Termination reason when stream ends (e.g. 'stop', 'length').",
    )
    is_final: bool = Field(
        default=False,
        description="Whether this is the terminating chunk of the stream.",
    )
    usage: LLMUsage | None = Field(
        default=None,
        description="Final token usage metadata attached to final chunk if available.",
    )


class LLMResponse(BaseModel):
    """Standardized response container returned by all LLM Providers."""

    model_config = ConfigDict(frozen=True)

    content: str = Field(
        ...,
        description="Generated text content.",
    )
    structured_data: dict[str, Any] | None = Field(
        default=None,
        description="Parsed JSON/structured output if structured generation was requested.",
    )
    usage: LLMUsage = Field(
        default_factory=LLMUsage,
        description="Token usage statistics.",
    )
    model_name: str = Field(
        ...,
        description="Model name that generated the response.",
    )
    finish_reason: str = Field(
        default="stop",
        description="Generation finish reason (e.g. 'stop', 'length', 'safety').",
    )
    latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Inference latency in milliseconds.",
    )
    raw_response: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw response payload from provider.",
    )


class Citation(BaseModel):
    """High-fidelity citation linking an answer statement to an underlying knowledge chunk."""

    model_config = ConfigDict(frozen=True)

    source_index: int = Field(
        ...,
        ge=1,
        description="1-based citation index corresponding to [1], [2], etc.",
    )
    citation_tag: str = Field(
        ...,
        description="Citation tag text (e.g. '[1]').",
    )
    chunk_id: str = Field(
        ...,
        description="Unique knowledge chunk identifier.",
    )
    document_id: str = Field(
        ...,
        description="Unique parent document identifier.",
    )
    title: str | None = Field(
        default=None,
        description="Document title.",
    )
    file_name: str | None = Field(
        default=None,
        description="Source document file name.",
    )
    page_number: int | None = Field(
        default=None,
        description="Document page number.",
    )
    heading: str | None = Field(
        default=None,
        description="Section heading.",
    )
    category: str | None = Field(
        default=None,
        description="Category/domain.",
    )
    score: float = Field(
        ...,
        description="Retrieval relevance score.",
    )
    relevance_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Normalized confidence score (0.0 to 1.0).",
    )
    snippet: str = Field(
        ...,
        description="Relevant text excerpt from the source chunk.",
    )


class GuardrailCheck(BaseModel):
    """Diagnostic outcome of an individual guardrail evaluation."""

    model_config = ConfigDict(frozen=True)

    check_name: str = Field(
        ...,
        description="Identifier of the guardrail check.",
    )
    passed: bool = Field(
        ...,
        description="Whether the verification passed.",
    )
    reason: str | None = Field(
        default=None,
        description="Explanation or failure reason.",
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed diagnostic data.",
    )


class GuardrailResult(BaseModel):
    """Aggregated outcome of pre-generation and post-generation guardrail pipelines."""

    model_config = ConfigDict(frozen=True)

    is_safe: bool = Field(
        default=True,
        description="True if all mandatory guardrail policies passed.",
    )
    insufficient_context: bool = Field(
        default=False,
        description="True if context was deemed inadequate to safely answer query.",
    )
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence score for the generated answer.",
    )
    checks: list[GuardrailCheck] = Field(
        default_factory=list,
        description="List of all individual guardrail evaluation checks.",
    )
    fallback_used: bool = Field(
        default=False,
        description="True if a safe fallback answer was returned instead of raw generation.",
    )
    fallback_reason: str | None = Field(
        default=None,
        description="Reason why fallback was triggered.",
    )


class RAGMetrics(BaseModel):
    """Performance telemetry and stage latencies for a RAG execution."""

    model_config = ConfigDict(frozen=True)

    retrieval_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time spent in hybrid retrieval.",
    )
    context_build_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time spent deduplicating and budgeting context.",
    )
    prompt_build_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time spent constructing prompt.",
    )
    llm_generation_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time spent in LLM provider inference.",
    )
    guardrails_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time spent executing guardrails.",
    )
    citations_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time spent extracting citations.",
    )
    total_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Total end-to-end execution latency.",
    )
    retrieved_chunks_count: int = Field(
        default=0,
        ge=0,
        description="Number of chunks retrieved from search.",
    )
    used_chunks_count: int = Field(
        default=0,
        ge=0,
        description="Number of chunks included in prompt context.",
    )
    dropped_chunks_count: int = Field(
        default=0,
        ge=0,
        description="Number of chunks dropped due to budget constraints.",
    )
    citations_count: int = Field(
        default=0,
        ge=0,
        description="Number of valid citations extracted.",
    )
    prompt_tokens: int = Field(
        default=0,
        ge=0,
        description="Input prompt token count.",
    )
    completion_tokens: int = Field(
        default=0,
        ge=0,
        description="Generated completion token count.",
    )
    total_tokens: int = Field(
        default=0,
        ge=0,
        description="Total tokens processed.",
    )


class RAGTrace(BaseModel):
    """Complete observability trace for audit, debugging, and dashboarding."""

    model_config = ConfigDict(frozen=True)

    query: str = Field(
        ...,
        description="User query string.",
    )
    provider: str = Field(
        ...,
        description="Active LLM provider name.",
    )
    model: str = Field(
        ...,
        description="Active LLM model name.",
    )
    prompt_strategy: str = Field(
        ...,
        description="Prompt strategy applied.",
    )
    retrieval_strategy: str = Field(
        default="hybrid",
        description="Retrieval mode applied.",
    )
    guardrail_strategies: list[str] = Field(
        default_factory=list,
        description="Active guardrail strategy identifiers.",
    )
    latencies: dict[str, float] = Field(
        default_factory=dict,
        description="Detailed stage-by-stage latencies in milliseconds.",
    )
    token_usage: LLMUsage = Field(
        default_factory=LLMUsage,
        description="Token usage metrics.",
    )
    retrieved_chunks: int = Field(
        default=0,
        ge=0,
        description="Count of retrieved chunks.",
    )
    used_chunks: int = Field(
        default=0,
        ge=0,
        description="Count of chunks used in context.",
    )
    citations_extracted: int = Field(
        default=0,
        ge=0,
        description="Count of citations generated.",
    )
    cache_hit: bool = Field(
        default=False,
        description="Whether retrieval used cached results.",
    )
    fallback_used: bool = Field(
        default=False,
        description="Whether safe fallback response was triggered.",
    )
    fallback_reason: str | None = Field(
        default=None,
        description="Reason for fallback invocation.",
    )
    guardrail_results: list[GuardrailCheck] = Field(
        default_factory=list,
        description="Guardrail check results.",
    )


class RAGRequest(BaseModel):
    """Request payload for RAG question answering and investigation queries."""

    model_config = ConfigDict(frozen=True)

    query: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="User inquiry or investigation question.",
    )
    provider: str | None = Field(
        default=None,
        description="Optional runtime LLM provider override ('gemini', 'ollama', 'mock').",
    )
    model: str | None = Field(
        default=None,
        description="Optional runtime model name override (e.g. 'gemini-1.5-pro', 'llama3').",
    )
    prompt_strategy: str | None = Field(
        default=None,
        description="Optional prompt strategy override ('standard_qa', 'investigative_analysis', etc.).",
    )
    filters: SearchFilters | None = Field(
        default=None,
        description="Metadata filters to constrain retrieval scope.",
    )
    retrieval_options: SearchOptions | None = Field(
        default=None,
        description="Options for retrieval depth, limits, and weights.",
    )
    generation_options: LLMGenerationOptions | None = Field(
        default=None,
        description="Options for LLM temperature, top_p, and token caps.",
    )
    conversation_history: list[LLMMessage] = Field(
        default_factory=list,
        description="Prior conversational turns for multi-turn chat.",
    )


class RAGResponse(BaseModel):
    """Complete RAG response containing answer, citations, context, metrics, and trace."""

    model_config = ConfigDict(frozen=True)

    query: str = Field(
        ...,
        description="Original query text.",
    )
    answer: str = Field(
        ...,
        description="Generated answer with inline citations.",
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Structured citations linking statements to source documents.",
    )
    used_chunks: list[ContextChunk] = Field(
        default_factory=list,
        description="Knowledge chunks that formed the context window.",
    )
    retrieval_result: RetrievalResult = Field(
        ...,
        description="Full retrieval result from the hybrid search engine.",
    )
    guardrail_result: GuardrailResult = Field(
        ...,
        description="Outcome of guardrail checks.",
    )
    metrics: RAGMetrics = Field(
        ...,
        description="Latency and token telemetry.",
    )
    trace: RAGTrace = Field(
        ...,
        description="Comprehensive execution trace.",
    )
    provider: str = Field(
        ...,
        description="LLM provider that executed generation.",
    )
    model: str = Field(
        ...,
        description="LLM model used.",
    )
    prompt_strategy: str = Field(
        ...,
        description="Prompt strategy applied.",
    )
