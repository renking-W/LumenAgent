"""OpenAI Responses API client for GPT/Codex model access."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from lumen_agent.config import Settings
from lumen_agent.domain.messages import ensure_blocks
from lumen_agent.infrastructure.http_pool import StreamHandle, get_http_pool

StreamHandleCallback = Callable[[StreamHandle], Awaitable[None]]


def to_responses_tools(internal_tools: list[dict]) -> list[dict]:
    """Convert internal tool schemas to Responses API function tools."""
    return [
        {
            "type": "function",
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get(
                "input_schema", {"type": "object", "properties": {}}
            ),
        }
        for tool in internal_tools
    ]


def _sendable_image_url(url: str) -> bool:
    return url.startswith(("http://", "https://", "data:"))


def to_responses_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert internal messages to stateless Responses API input items."""
    result: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role", "user")
        raw_content = message.get("content", [])
        blocks = (
            [block for block in raw_content if isinstance(block, dict)]
            if isinstance(raw_content, list)
            else ensure_blocks(raw_content)
        )
        text = "".join(
            str(block.get("text", ""))
            for block in blocks
            if block.get("type") == "text"
        )

        image_urls = [
            str((block.get("image_url") or {}).get("url", ""))
            for block in blocks
            if block.get("type") == "image_url"
        ]
        image_urls = [url for url in image_urls if _sendable_image_url(url)]

        if role == "user" and image_urls:
            content: list[dict[str, Any]] = []
            if text:
                content.append({"type": "input_text", "text": text})
            content.extend(
                {"type": "input_image", "image_url": url} for url in image_urls
            )
            result.append({"role": "user", "content": content})
        elif text or role in {"system", "developer", "user"}:
            result.append({"role": role, "content": text})

        for block in blocks:
            block_type = block.get("type")
            if block_type == "tool_use":
                result.append(
                    {
                        "type": "function_call",
                        "call_id": block.get("id", ""),
                        "name": block.get("name", ""),
                        "arguments": json.dumps(
                            block.get("input", {}), ensure_ascii=False
                        ),
                    }
                )
            elif block_type == "tool_result":
                result.append(
                    {
                        "type": "function_call_output",
                        "call_id": block.get("tool_use_id", ""),
                        "output": str(block.get("content", "")),
                    }
                )
    return result


def response_content_blocks(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract reasoning summaries and assistant text from a response."""
    reasoning_parts: list[str] = []
    text_parts: list[str] = []
    for item in data.get("output") or []:
        item_type = item.get("type")
        if item_type == "reasoning":
            for summary in item.get("summary") or []:
                value = summary.get("text")
                if isinstance(value, str) and value:
                    reasoning_parts.append(value)
        elif item_type == "message":
            for content in item.get("content") or []:
                if content.get("type") in {"output_text", "refusal"}:
                    value = content.get("text") or content.get("refusal")
                    if isinstance(value, str) and value:
                        text_parts.append(value)

    blocks: list[dict[str, Any]] = []
    if reasoning_parts:
        blocks.append({"type": "thinking", "thinking": "".join(reasoning_parts)})
    if text_parts:
        blocks.append({"type": "text", "text": "".join(text_parts)})
    return blocks


class OpenAIResponsesHttpClient:
    """OpenAI client using the Responses API and the shared HTTP pool."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _url(self) -> str:
        base_url = str(
            self._settings.get("LLM_BASE_URL", "https://api.openai.com/v1")
        ).rstrip("/")
        return (
            f"{base_url}/responses"
            if base_url.endswith("/v1")
            else f"{base_url}/v1/responses"
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.get('LLM_API_KEY', '')}",
            "Content-Type": "application/json",
        }

    def _payload(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None,
        stream: bool,
        tools: list[dict] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._settings.get("LLM_MODEL", "gpt-5.6"),
            "input": to_responses_input(messages),
            "store": False,
        }
        if stream:
            payload["stream"] = True
        effective_temperature = (
            temperature
            if temperature is not None
            else self._settings.get("LLM_TEMPERATURE")
        )
        if effective_temperature is not None:
            payload["temperature"] = effective_temperature
        max_tokens = self._settings.get("LLM_MAX_TOKENS")
        if max_tokens is not None:
            payload["max_output_tokens"] = max_tokens
        if self._settings.get("LLM_ENABLE_THINKING", True):
            payload["reasoning"] = {"summary": "auto"}
        if tools:
            payload["tools"] = to_responses_tools(tools)
            tool_choice = self._settings.get("AGENT_TOOL_CHOICE")
            if tool_choice:
                payload["tool_choice"] = tool_choice
        return payload

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
    ) -> str:
        blocks = await self.chat_blocks(messages, temperature=temperature)
        text = "".join(
            block["text"] for block in blocks if block.get("type") == "text"
        )
        if not text.strip():
            raise RuntimeError("OpenAI Responses API returned no assistant text")
        return text

    async def chat_blocks(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
    ) -> list[dict[str, Any]]:
        response = await get_http_pool().send(
            "POST",
            self._url(),
            headers=self._headers(),
            json=self._payload(messages, temperature=temperature, stream=False),
        )
        response.raise_for_status()
        blocks = response_content_blocks(response.json())
        if not blocks:
            raise RuntimeError("OpenAI Responses API returned an empty response")
        return blocks

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
        tools: list[dict] | None = None,
        on_connect: StreamHandleCallback | None = None,
    ) -> AsyncIterator[tuple[str, str | dict]]:
        handle = get_http_pool().send_stream(
            "POST",
            self._url(),
            headers=self._headers(),
            json=self._payload(
                messages, temperature=temperature, stream=True, tools=tools
            ),
            protocol="responses",
        )
        await handle.connect()
        if on_connect is not None:
            await on_connect(handle)
        kind_map = {"content": "text", "reasoning_content": "thinking"}
        async for kind, data in handle.receive():
            yield (kind_map.get(kind, kind), data)
