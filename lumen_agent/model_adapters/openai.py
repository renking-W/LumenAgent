"""OpenAI Responses API model adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from lumen_agent.model_adapters.base import ModelAdapter, StreamHandleCallback
from lumen_agent.model_adapters.client.openai_responses_client import (
    OpenAIResponsesHttpClient,
)


class OpenAIAdapter(ModelAdapter):
    """Expose the OpenAI Responses client through the common model interface."""

    def __init__(self, client: OpenAIResponsesHttpClient) -> None:
        self._client = client

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
    ) -> str:
        return await self._client.chat(messages, temperature=temperature)

    async def chat_blocks(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
    ) -> list[dict[str, Any]]:
        return await self._client.chat_blocks(messages, temperature=temperature)

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict] | None = None,
        temperature: float | None = None,
        on_connect: StreamHandleCallback | None = None,
    ) -> AsyncIterator[tuple[str, str | dict]]:
        return self._client.chat_stream(
            messages,
            tools=tools,
            temperature=temperature,
            on_connect=on_connect,
        )
