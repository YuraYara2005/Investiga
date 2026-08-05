"""Ollama Local LLM Provider Implementation.

Communicates asynchronously with a local or self-hosted Ollama server instance
supporting models such as Llama 3, Mistral, and DeepSeek.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import RAGSettings
from app.core.logging import get_logger
from app.rag.context_builder import count_tokens
from app.rag.exceptions import (
    LLMProviderException,
    LLMTimeoutException,
)
from app.rag.models import (
    FormattedPrompt,
    LLMGenerationOptions,
    LLMResponse,
    LLMUsage,
    MessageRole,
    StreamChunk,
)
from app.rag.providers.base import LLMProvider

logger = get_logger(__name__)


class OllamaLLMProvider(LLMProvider):
    """Local and self-hosted Ollama LLM provider."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3",
        timeout: float = 60.0,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        client: httpx.AsyncClient | None = None,
        settings: RAGSettings | None = None,
    ) -> None:
        """Initialize OllamaLLMProvider.

        Args:
            base_url: Ollama daemon URL.
            default_model: Default Ollama model name.
            timeout: Request timeout in seconds.
            max_retries: Max retry attempts on failure.
            backoff_factor: Retry backoff multiplier.
            client: Optional pre-configured HTTPX client.
            settings: Optional RAGSettings container.
        """
        if settings is not None:
            self._base_url = settings.ollama_base_url.rstrip("/")
            self._default_model = default_model or settings.ollama_model
            self._timeout = timeout or settings.timeout_seconds
            self._max_retries = max_retries or settings.retry_max_attempts
            self._backoff_factor = backoff_factor or settings.retry_backoff_factor
        else:
            self._base_url = base_url.rstrip("/")
            self._default_model = default_model
            self._timeout = timeout
            self._max_retries = max_retries
            self._backoff_factor = backoff_factor

        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout, connect=10.0),
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=10),
        )
        self._owns_client = client is None

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def default_model(self) -> str:
        return self._default_model

    def _build_messages(self, prompt: FormattedPrompt) -> list[dict[str, str]]:
        """Format messages payload for Ollama /api/chat."""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": prompt.system_prompt}
        ]
        for msg in prompt.messages:
            if msg.role == MessageRole.SYSTEM:
                continue
            role_str = "assistant" if msg.role == MessageRole.ASSISTANT else "user"
            messages.append({"role": role_str, "content": msg.content})

        if len(messages) == 1:
            messages.append({"role": "user", "content": prompt.user_prompt})

        return messages

    async def generate(
        self,
        prompt: FormattedPrompt,
        options: LLMGenerationOptions | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        """Execute non-streaming chat generation via Ollama."""
        opts = options or LLMGenerationOptions()
        active_model = model or self._default_model
        endpoint_url = f"{self._base_url}/api/chat"

        payload: dict[str, Any] = {
            "model": active_model,
            "messages": self._build_messages(prompt),
            "stream": False,
            "options": {
                "temperature": opts.temperature,
                "top_p": opts.top_p,
                "num_predict": opts.max_output_tokens,
            },
        }
        if opts.stop_sequences:
            payload["options"]["stop"] = opts.stop_sequences

        start_time = time.perf_counter()
        last_exc: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._client.post(
                    endpoint_url,
                    json=payload,
                    timeout=opts.timeout_seconds,
                )

                if response.status_code == 200:
                    data = response.json()
                    latency_ms = (time.perf_counter() - start_time) * 1000.0

                    content = data.get("message", {}).get("content", "")
                    prompt_eval_count = data.get("prompt_eval_count", prompt.estimated_prompt_tokens)
                    eval_count = data.get("eval_count", count_tokens(content))
                    total_tokens = prompt_eval_count + eval_count

                    usage = LLMUsage(
                        prompt_tokens=prompt_eval_count,
                        completion_tokens=eval_count,
                        total_tokens=total_tokens,
                        estimated="prompt_eval_count" not in data,
                    )

                    return LLMResponse(
                        content=content,
                        structured_data=None,
                        usage=usage,
                        model_name=active_model,
                        finish_reason=data.get("done_reason", "stop"),
                        latency_ms=round(latency_ms, 2),
                        raw_response=data,
                    )

                if response.status_code >= 500 and attempt < self._max_retries:
                    await asyncio.sleep(self._backoff_factor**attempt)
                    continue

                raise LLMProviderException(
                    provider=self.name,
                    model=active_model,
                    status_code=response.status_code,
                    message=f"Ollama server returned error: {response.text}",
                )

            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt == self._max_retries:
                    raise LLMTimeoutException(
                        provider=self.name,
                        model=active_model,
                        timeout_seconds=opts.timeout_seconds,
                    ) from exc
                await asyncio.sleep(self._backoff_factor**attempt)

            except httpx.RequestError as exc:
                last_exc = exc
                if attempt == self._max_retries:
                    raise LLMProviderException(
                        provider=self.name,
                        model=active_model,
                        message=f"Failed to connect to Ollama daemon at {self._base_url}: {exc}",
                    ) from exc
                await asyncio.sleep(self._backoff_factor**attempt)

        raise LLMProviderException(
            provider=self.name,
            model=active_model,
            message=f"Ollama generation failed after retries: {last_exc}",
        )

    async def stream_generate(
        self,
        prompt: FormattedPrompt,
        options: LLMGenerationOptions | None = None,
        model: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Execute streaming generation via Ollama /api/chat."""
        opts = options or LLMGenerationOptions()
        active_model = model or self._default_model
        endpoint_url = f"{self._base_url}/api/chat"

        payload: dict[str, Any] = {
            "model": active_model,
            "messages": self._build_messages(prompt),
            "stream": True,
            "options": {
                "temperature": opts.temperature,
                "top_p": opts.top_p,
                "num_predict": opts.max_output_tokens,
            },
        }

        try:
            async with self._client.stream(
                "POST",
                endpoint_url,
                json=payload,
                timeout=opts.timeout_seconds,
            ) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    raise LLMProviderException(
                        provider=self.name,
                        model=active_model,
                        status_code=response.status_code,
                        message=f"Ollama stream failed: {err_body.decode('utf-8', errors='ignore')}",
                    )

                accumulated = ""
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk_json = json.loads(line)
                        msg = chunk_json.get("message", {})
                        delta = msg.get("content", "")
                        done = chunk_json.get("done", False)

                        if delta:
                            accumulated += delta
                            yield StreamChunk(
                                content=delta,
                                finish_reason=None,
                                is_final=False,
                            )

                        if done:
                            p_cnt = chunk_json.get("prompt_eval_count", prompt.estimated_prompt_tokens)
                            e_cnt = chunk_json.get("eval_count", count_tokens(accumulated))
                            yield StreamChunk(
                                content="",
                                finish_reason=chunk_json.get("done_reason", "stop"),
                                is_final=True,
                                usage=LLMUsage(
                                    prompt_tokens=p_cnt,
                                    completion_tokens=e_cnt,
                                    total_tokens=p_cnt + e_cnt,
                                    estimated=False,
                                ),
                            )
                            break
                    except Exception:
                        continue

        except httpx.TimeoutException as exc:
            raise LLMTimeoutException(
                provider=self.name,
                model=active_model,
                timeout_seconds=opts.timeout_seconds,
            ) from exc

    async def is_healthy(self) -> bool:
        """Probe Ollama server availability."""
        try:
            res = await self._client.get(f"{self._base_url}/api/tags", timeout=3.0)
            return res.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close underlying HTTP client."""
        if self._owns_client and not self._client.is_closed:
            await self._client.aclose()
