"""LLM Provider - OpenAI compatible API client."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

from openai import AsyncOpenAI, RateLimitError, APIConnectionError, APITimeoutError, InternalServerError

_RETRYABLE_ERRORS = (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)

logger = logging.getLogger("hellocode.provider")

from .config import Config


class LLMProvider:
    def __init__(self, config: Config):
        self.config = config
        kwargs: dict[str, Any] = {}
        base_url = config.get_provider_base_url()
        if base_url:
            kwargs["base_url"] = base_url
        headers = config.get_provider_headers()
        if headers:
            kwargs["default_headers"] = headers
        api_key = config.get_provider_key()
        if not api_key:
            logger.warning("No API key configured. LLM calls will fail.")
            api_key = "sk-placeholder"
        self.client = AsyncOpenAI(api_key=api_key, **kwargs)
        self._max_retries = 3
        self._base_delay = 2.0

    def get_model(self, agent_name: str | None = None) -> str:
        return self.config.get_provider_model(agent_name)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 32768,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        stream: bool = False,
    ) -> dict[str, Any] | AsyncIterator[dict[str, Any]]:
        kwargs: dict[str, Any] = {
            "model": model or self.get_model(),
            "messages": messages,
            "temperature": temperature,
        }
        # Use max_completion_tokens if available (some APIs prefer this), else max_tokens
        if max_tokens and max_tokens > 0:
            kwargs["max_tokens"] = max_tokens
        if tools:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        if stream:
            return self._stream_with_retry(kwargs)

        for attempt in range(self._max_retries):
            try:
                resp = await self.client.chat.completions.create(**kwargs)
                logger.debug("LLM response: model=%s, choices=%d", resp.model, len(resp.choices))
                if not resp.choices:
                    raise ValueError("LLM returned empty choices")
                choice = resp.choices[0]
                result: dict[str, Any] = {
                    "role": "assistant",
                    "content": choice.message.content or "",
                }
                if choice.message.tool_calls:
                    result["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in choice.message.tool_calls
                    ]
                return result
            except _RETRYABLE_ERRORS as e:
                if attempt < self._max_retries - 1:
                    delay = self._base_delay * (2 ** attempt)
                    logger.warning("Request failed (%s), retrying in %.1fs (attempt %d/%d)", type(e).__name__, delay, attempt + 1, self._max_retries)
                    await asyncio.sleep(delay)
                else:
                    raise

    async def _stream(self, kwargs: dict) -> AsyncIterator[dict[str, Any]]:
        stream = await self.client.chat.completions.create(**kwargs, stream=True)
        tool_calls: dict[int, dict[str, Any]] = {}
        try:
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if not delta:
                    continue
                if delta.content:
                    yield {"type": "content", "content": delta.content}
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        if tc.index is None:
                            continue
                        current = tool_calls.setdefault(
                            tc.index,
                            {
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            },
                        )
                        if tc.id:
                            current["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                current["function"]["name"] = tc.function.name
                            if tc.function.arguments:
                                current["function"]["arguments"] += tc.function.arguments
        finally:
            await stream.close()
        for idx in sorted(tool_calls):
            yield {"type": "tool_call", "tool_call": tool_calls[idx]}

    async def _stream_with_retry(self, kwargs: dict) -> AsyncIterator[dict[str, Any]]:
        for attempt in range(self._max_retries):
            data_yielded = False
            try:
                async for chunk in self._stream(kwargs):
                    data_yielded = True
                    yield chunk
                return
            except _RETRYABLE_ERRORS as e:
                if data_yielded:
                    raise
                if attempt < self._max_retries - 1:
                    delay = self._base_delay * (2 ** attempt)
                    logger.warning("Stream failed (%s), retrying in %.1fs (attempt %d/%d)", type(e).__name__, delay, attempt + 1, self._max_retries)
                    await asyncio.sleep(delay)
                else:
                    raise

    def build_tool_schema(self, tools: list[Any]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.id,
                    "description": t.description,
                    "parameters": t.parameters_schema(),
                },
            }
            for t in tools
        ]
