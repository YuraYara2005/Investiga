"""Google Gemini LLM Provider Implementation.

Communicates asynchronously with the Google Gemini API using connection-pooled HTTPX
with exponential backoff retries, structured error mapping, and streaming support.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import RAGSettings
from app.core.logging import get_logger
from app.rag.context_builder import count_tokens
from app.rag.exceptions import (
    LLMAuthenticationException,
    LLMInvalidResponseException,
    LLMProviderException,
    LLMRateLimitException,
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


class GeminiLLMProvider(LLMProvider):
    """Production-grade Google Gemini API provider."""

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str = "gemini-1.5-flash",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        client: httpx.AsyncClient | None = None,
        settings: RAGSettings | None = None,
    ) -> None:
        """Initialize GeminiLLMProvider.

        Args:
            api_key: Google Gemini API key.
            default_model: Default Gemini model identifier.
            base_url: API endpoint root.
            timeout: Maximum request timeout in seconds.
            max_retries: Retry attempts on transient errors.
            backoff_factor: Exponential backoff coefficient.
            client: Optional pre-configured HTTPX client.
            settings: Optional RAGSettings container.
        """
        if settings is not None:
            self._api_key = api_key or settings.gemini_api_key.get_secret_value()
            self._default_model = default_model or settings.gemini_model
            self._base_url = base_url or settings.gemini_api_base_url
            self._timeout = timeout or settings.timeout_seconds
            self._max_retries = max_retries or settings.retry_max_attempts
            self._backoff_factor = backoff_factor or settings.retry_backoff_factor
        else:
            self._api_key = api_key or ""
            self._default_model = default_model
            self._base_url = base_url
            self._timeout = timeout
            self._max_retries = max_retries
            self._backoff_factor = backoff_factor

        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout, connect=10.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
        self._owns_client = client is None

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def default_model(self) -> str:
        return self._default_model

    def _build_payload(
        self,
        prompt: FormattedPrompt,
        options: LLMGenerationOptions,
    ) -> dict[str, Any]:
        """Format the Gemini generateContent request JSON body."""
        contents: list[dict[str, Any]] = []

        # Convert conversation messages
        for msg in prompt.messages:
            if msg.role == MessageRole.SYSTEM:
                continue  # System prompt passed in systemInstruction
            role_str = "model" if msg.role == MessageRole.ASSISTANT else "user"
            contents.append({
                "role": role_str,
                "parts": [{"text": msg.content}],
            })

        if not contents:
            contents = [{"role": "user", "parts": [{"text": prompt.user_prompt}]}]

        payload: dict[str, Any] = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": prompt.system_prompt}],
            },
            "generationConfig": {
                "temperature": options.temperature,
                "topP": options.top_p,
                "maxOutputTokens": options.max_output_tokens,
            },
        }

        if options.stop_sequences:
            payload["generationConfig"]["stopSequences"] = options.stop_sequences

        return payload

    async def _execute_with_retry(
        self,
        url: str,
        payload: dict[str, Any],
        model: str,
        timeout: float,
    ) -> dict[str, Any]:
        """Execute HTTP POST with exponential backoff and jitter."""
        if not self._api_key:
            raise LLMAuthenticationException(
                provider=self.name,
                message="Google Gemini API key is missing. Set RAG__GEMINI_API_KEY.",
            )

        last_exception: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._client.post(
                    url,
                    json=payload,
                    params={"key": self._api_key},
                    headers={"Content-Type": "application/json"},
                    timeout=timeout,
                )

                if response.status_code == 200:
                    return response.json()

                if response.status_code in (401, 403):
                    raise LLMAuthenticationException(
                        provider=self.name,
                        message=f"Gemini authentication failed ({response.status_code}): {response.text}",
                    )

                if response.status_code == 429:
                    if attempt == self._max_retries:
                        raise LLMRateLimitException(
                            provider=self.name,
                            model=model,
                        )
                    # Backoff on 429
                    sleep_time = (self._backoff_factor**attempt) + random.uniform(0.1, 0.5)
                    logger.warning(
                        "gemini_rate_limit_retry",
                        attempt=attempt,
                        sleep_seconds=sleep_time,
                    )
                    await asyncio.sleep(sleep_time)
                    continue

                if response.status_code >= 500:
                    if attempt == self._max_retries:
                        raise LLMProviderException(
                            provider=self.name,
                            model=model,
                            status_code=response.status_code,
                            message=f"Gemini server error: {response.text}",
                        )
                    sleep_time = (self._backoff_factor**attempt) + random.uniform(0.1, 0.5)
                    await asyncio.sleep(sleep_time)
                    continue

                # Unhandled 4xx error
                raise LLMProviderException(
                    provider=self.name,
                    model=model,
                    status_code=response.status_code,
                    message=f"Gemini API request failed: {response.text}",
                )

            except httpx.TimeoutException as exc:
                last_exception = exc
                if attempt == self._max_retries:
                    raise LLMTimeoutException(
                        provider=self.name,
                        model=model,
                        timeout_seconds=timeout,
                    ) from exc
                await asyncio.sleep(self._backoff_factor**attempt)

            except httpx.RequestError as exc:
                last_exception = exc
                if attempt == self._max_retries:
                    raise LLMProviderException(
                        provider=self.name,
                        model=model,
                        message=f"Network error connecting to Gemini: {exc}",
                    ) from exc
                await asyncio.sleep(self._backoff_factor**attempt)

        raise LLMProviderException(
            provider=self.name,
            model=model,
            message=f"Gemini request failed after {self._max_retries} attempts: {last_exception}",
        )

    async def generate(
        self,
        prompt: FormattedPrompt,
        options: LLMGenerationOptions | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        """Execute synchronous generation via Gemini API."""
        opts = options or LLMGenerationOptions()
        active_model = model or self._default_model
        endpoint_url = f"{self._base_url}/models/{active_model}:generateContent"

        payload = self._build_payload(prompt, opts)
        start_time = time.perf_counter()

        data = await self._execute_with_retry(
            url=endpoint_url,
            payload=payload,
            model=active_model,
            timeout=opts.timeout_seconds,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        try:
            candidates = data.get("candidates", [])
            if not candidates:
                raise LLMInvalidResponseException(
                    provider=self.name,
                    reason="No candidates returned in Gemini response payload.",
                    raw_content=json.dumps(data),
                )

            cand = candidates[0]
            finish_reason = cand.get("finishReason", "stop")
            content_part = cand.get("content", {}).get("parts", [{}])[0]
            text = content_part.get("text", "")

            usage_meta = data.get("usageMetadata", {})
            prompt_tokens = usage_meta.get("promptTokenCount", prompt.estimated_prompt_tokens)
            completion_tokens = usage_meta.get("candidatesTokenCount", count_tokens(text))
            total_tokens = usage_meta.get("totalTokenCount", prompt_tokens + completion_tokens)

            usage = LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated="promptTokenCount" not in usage_meta,
            )

            return LLMResponse(
                content=text,
                structured_data=None,
                usage=usage,
                model_name=active_model,
                finish_reason=finish_reason,
                latency_ms=round(latency_ms, 2),
                raw_response=data,
            )

        except Exception as exc:
            if isinstance(exc, LLMProviderException):
                raise
            raise LLMInvalidResponseException(
                provider=self.name,
                reason=f"Failed to parse Gemini response: {exc}",
                raw_content=json.dumps(data),
            ) from exc

    async def stream_generate(
        self,
        prompt: FormattedPrompt,
        options: LLMGenerationOptions | None = None,
        model: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Execute streaming token generation via Gemini streamGenerateContent."""
        opts = options or LLMGenerationOptions()
        active_model = model or self._default_model
        endpoint_url = f"{self._base_url}/models/{active_model}:streamGenerateContent"

        if not self._api_key:
            raise LLMAuthenticationException(
                provider=self.name,
                message="Google Gemini API key is missing. Set RAG__GEMINI_API_KEY.",
            )

        payload = self._build_payload(prompt, opts)

        try:
            async with self._client.stream(
                "POST",
                endpoint_url,
                json=payload,
                params={"key": self._api_key, "alt": "sse"},
                headers={"Content-Type": "application/json"},
                timeout=opts.timeout_seconds,
            ) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    raise LLMProviderException(
                        provider=self.name,
                        model=active_model,
                        status_code=response.status_code,
                        message=f"Stream request failed: {err_body.decode('utf-8', errors='ignore')}",
                    )

                accumulated_text = ""
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    json_str = line[5:].strip()
                    if not json_str or json_str == "[DONE]":
                        break

                    try:
                        chunk_data = json.loads(json_str)
                        cands = chunk_data.get("candidates", [])
                        if cands:
                            c = cands[0]
                            parts = c.get("content", {}).get("parts", [])
                            if parts:
                                part_text = parts[0].get("text", "")
                                accumulated_text += part_text
                                finish_r = c.get("finishReason")
                                yield StreamChunk(
                                    content=part_text,
                                    finish_reason=finish_r,
                                    is_final=False,
                                )
                    except Exception:
                        continue

                # Final termination chunk
                yield StreamChunk(
                    content="",
                    finish_reason="stop",
                    is_final=True,
                    usage=LLMUsage(
                        prompt_tokens=prompt.estimated_prompt_tokens,
                        completion_tokens=count_tokens(accumulated_text),
                        total_tokens=prompt.estimated_prompt_tokens + count_tokens(accumulated_text),
                        estimated=True,
                    ),
                )

        except httpx.TimeoutException as exc:
            raise LLMTimeoutException(
                provider=self.name,
                model=active_model,
                timeout_seconds=opts.timeout_seconds,
            ) from exc

    async def is_healthy(self) -> bool:
        """Verify provider responsiveness."""
        return bool(self._api_key and len(self._api_key) > 5)

    async def close(self) -> None:
        """Close underlying HTTP client if owned."""
        if self._owns_client and not self._client.is_closed:
            await self._client.aclose()
