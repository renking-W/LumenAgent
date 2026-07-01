"""Agnes OpenAI 兼容 `POST /v1/chat/completions` 客户端。

与 DeepSeek 的主要区别：
  - Thinking 模式通过 `chat_template_kwargs.enable_thinking` 开启
  - API 端点：https://apihub.agnes-ai.com/v1/chat/completions
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Awaitable
from typing import Any

from lumen_agent.config import Settings
from lumen_agent.infrastructure.http_pool import StreamHandle, get_http_pool
from lumen_agent.model_adapters.client.openai_format import to_openai_messages, to_openai_tools

StreamHandleCallback = Callable[[StreamHandle], Awaitable[None]]


class AgnesHttpClient:
    """Agnes OpenAI 兼容 Chat Completions 客户端。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _chat_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.get('LLM_API_KEY', '')}",
            "Content-Type": "application/json",
        }

    def _build_chat_payload(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None,
        stream: bool = False,
        tools: list[dict] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._settings.get("LLM_MODEL", "agnes-2.0-flash"),
            "messages": messages,
        }
        if stream:
            payload["stream"] = True
        effective_temperature = (
            temperature if temperature is not None else self._settings.get("LLM_TEMPERATURE")
        )
        if effective_temperature is not None:
            payload["temperature"] = effective_temperature
        if self._settings.get("LLM_MAX_TOKENS") is not None:
            payload["max_tokens"] = self._settings.get("LLM_MAX_TOKENS")
        if self._settings.get("LLM_TOP_P") is not None:
            payload["top_p"] = self._settings.get("LLM_TOP_P")
        # Agnes 通过 chat_template_kwargs.enable_thinking 开启思考链
        enable_thinking = self._settings.get("LLM_ENABLE_THINKING")
        if enable_thinking is not None:
            payload["chat_template_kwargs"] = {
                "enable_thinking": bool(enable_thinking),
            }
        if tools:
            payload["tools"] = to_openai_tools(tools)
            tool_choice = self._settings.get("AGENT_TOOL_CHOICE")
            if tool_choice:
                payload["tool_choice"] = tool_choice
        return payload

    def _base_url(self) -> str:
        return self._settings.get("LLM_BASE_URL", "https://apihub.agnes-ai.com")

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
    ) -> str:
        url = f"{self._base_url()}/v1/chat/completions"
        headers = self._chat_headers()
        api_messages = to_openai_messages(messages)
        payload = self._build_chat_payload(api_messages, temperature=temperature, stream=False)

        pool = get_http_pool()
        response = await pool.send("POST", url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("upstream returned no choices")

        message = (choices[0] or {}).get("message") or {}
        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("upstream returned empty or non-text assistant content")

        return content

    async def chat_blocks(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
    ) -> list[dict[str, Any]]:
        url = f"{self._base_url()}/v1/chat/completions"
        headers = self._chat_headers()
        api_messages = to_openai_messages(messages)
        payload = self._build_chat_payload(api_messages, temperature=temperature, stream=False)

        pool = get_http_pool()
        response = await pool.send("POST", url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("upstream returned no choices")

        message = (choices[0] or {}).get("message") or {}
        content_text = (message.get("content") or "").strip()
        reasoning_text = (message.get("reasoning_content") or "").strip()

        blocks: list[dict[str, Any]] = []
        if reasoning_text:
            blocks.append({"type": "thinking", "thinking": reasoning_text})
        if content_text:
            blocks.append({"type": "text", "text": content_text})

        if not blocks:
            raise RuntimeError("upstream returned empty assistant response")

        return blocks

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
        tools: list[dict] | None = None,
        on_connect: StreamHandleCallback | None = None,
    ) -> AsyncIterator[tuple[str, str | dict]]:
        url = f"{self._base_url()}/v1/chat/completions"
        headers = self._chat_headers()
        api_messages = to_openai_messages(messages)
        payload = self._build_chat_payload(
            api_messages, temperature=temperature, stream=True, tools=tools
        )

        pool = get_http_pool()
        handle = pool.send_stream("POST", url, headers=headers, json=payload)
        await handle.connect()
        if on_connect is not None:
            await on_connect(handle)
        _KIND_MAP = {"content": "text", "reasoning_content": "thinking"}
        async for kind, data in handle.receive():
            yield (_KIND_MAP.get(kind, kind), data)
