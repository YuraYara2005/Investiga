"""Mock LLM Provider for Fast, Deterministic Unit and Integration Testing.

Allows configuring predefined responses, custom usage, simulated stream tokens,
latency emulation, and synthetic error triggers without network calls.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from app.rag.context_builder import count_tokens
from app.rag.exceptions import LLMProviderException, LLMTimeoutException
from app.rag.models import (
    FormattedPrompt,
    LLMGenerationOptions,
    LLMResponse,
    LLMUsage,
    StreamChunk,
)
from app.rag.providers.base import LLMProvider


DEFAULT_MOCK_RESPONSE = (
    "Based on the evidence in [1], the database connection pool was exhausted due to unclosed sessions [2]."
)


class MockLLMProvider(LLMProvider):
    """Deterministic in-memory mock LLM provider for unit tests and local pipelines."""

    def __init__(
        self,
        canned_response: str = DEFAULT_MOCK_RESPONSE,
        default_model: str = "mock-gpt-4",
        simulated_latency_ms: float = 5.0,
        should_fail: bool = False,
        should_timeout: bool = False,
    ) -> None:
        """Initialize MockLLMProvider.

        Args:
            canned_response: Default text output for generate and stream_generate.
            default_model: Name of mock model.
            simulated_latency_ms: Artificial latency to emulate inference.
            should_fail: Trigger synthetic failure for error testing.
            should_timeout: Trigger synthetic timeout exception.
        """
        self._canned_response = canned_response
        self._default_model = default_model
        self._simulated_latency_ms = simulated_latency_ms
        self._should_fail = should_fail
        self._should_timeout = should_timeout
        self.call_count = 0
        self.last_prompt: FormattedPrompt | None = None
        self.last_options: LLMGenerationOptions | None = None

    @property
    def name(self) -> str:
        return "mock"

    @property
    def default_model(self) -> str:
        return self._default_model

    def set_canned_response(self, text: str) -> None:
        """Update the canned response string."""
        self._canned_response = text

    def set_failure(self, fail: bool) -> None:
        """Toggle synthetic failure state."""
        self._should_fail = fail

    def set_timeout(self, timeout: bool) -> None:
        """Toggle synthetic timeout state."""
        self._should_timeout = timeout

    def _resolve_response(self, prompt: FormattedPrompt) -> str:
        """Resolve response text, synthesizing grounded citations if using default mock."""
        if self._canned_response != DEFAULT_MOCK_RESPONSE:
            return self._canned_response

        import re
        source_matches = list(
            re.finditer(
                r"\[(\d+)\]\s*Source\s*\[([^\]]*)\]\s*\n(.*?)(?=\n\n\[|\n\n---\n\n|\n\nQUESTION:|\Z)",
                prompt.user_prompt,
                re.DOTALL,
            )
        )
        if not source_matches:
            return self._canned_response

        parts: list[str] = []
        for match in source_matches[:5]:
            src_num = match.group(1)
            body = match.group(3).strip()
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if len(s.strip()) > 15]
            if sentences:
                clean_sentence = sentences[0].rstrip(".")
                parts.append(f"According to [{src_num}], {clean_sentence}.")

        if parts:
            return " ".join(parts)
        return self._canned_response

    async def generate(
        self,
        prompt: FormattedPrompt,
        options: LLMGenerationOptions | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        """Simulate synchronous generation."""
        self.call_count += 1
        self.last_prompt = prompt
        self.last_options = options
        opts = options or LLMGenerationOptions()
        active_model = model or self._default_model

        if self._should_timeout:
            raise LLMTimeoutException(
                provider=self.name,
                model=active_model,
                timeout_seconds=opts.timeout_seconds,
            )

        if self._should_fail:
            raise LLMProviderException(
                provider=self.name,
                model=active_model,
                message="Mock synthetic generation failure.",
            )

        if self._simulated_latency_ms > 0:
            await asyncio.sleep(self._simulated_latency_ms / 1000.0)

        response_text = self._resolve_response(prompt)
        prompt_tokens = prompt.estimated_prompt_tokens
        completion_tokens = count_tokens(response_text)

        return LLMResponse(
            content=response_text,
            structured_data=None,
            usage=LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                estimated=False,
            ),
            model_name=active_model,
            finish_reason="stop",
            latency_ms=self._simulated_latency_ms,
            raw_response={"mock": True, "call_count": self.call_count},
        )

    async def stream_generate(
        self,
        prompt: FormattedPrompt,
        options: LLMGenerationOptions | None = None,
        model: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Simulate streaming generation word-by-word."""
        self.call_count += 1
        self.last_prompt = prompt
        self.last_options = options
        opts = options or LLMGenerationOptions()
        active_model = model or self._default_model

        if self._should_timeout:
            raise LLMTimeoutException(
                provider=self.name,
                model=active_model,
                timeout_seconds=opts.timeout_seconds,
            )

        if self._should_fail:
            raise LLMProviderException(
                provider=self.name,
                model=active_model,
                message="Mock synthetic streaming failure.",
            )

        response_text = self._resolve_response(prompt)
        words = response_text.split(" ")
        for idx, word in enumerate(words):
            chunk_text = word if idx == len(words) - 1 else f"{word} "
            yield StreamChunk(
                content=chunk_text,
                finish_reason=None,
                is_final=False,
            )
            if self._simulated_latency_ms > 0:
                await asyncio.sleep(0.001)

        # Final terminating chunk
        prompt_tokens = prompt.estimated_prompt_tokens
        completion_tokens = count_tokens(response_text)


        yield StreamChunk(
            content="",
            finish_reason="stop",
            is_final=True,
            usage=LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                estimated=False,
            ),
        )

    async def is_healthy(self) -> bool:
        """Mock health check is always healthy unless failing."""
        return not self._should_fail
