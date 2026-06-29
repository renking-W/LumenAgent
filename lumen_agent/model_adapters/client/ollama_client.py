"""Ollama OpenAI 兼容 `POST /v1/chat/completions` 客户端。

Ollama 从 0.14+ 提供 OpenAI 兼容端点，0.5+ 支持 reasoning_content。
与 DeepSeekHttpClient 的区别：
  - 不强制要求 Bearer Token 认证
  - 不支持 enable_thinking 参数
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Awaitable
from typing import Any

from lumen_agent.config import Settings
from lumen_agent.infrastructure.http_pool import StreamHandle, get_http_pool
from lumen_agent.model_adapters.client.openai_format import to_openai_messages, to_openai_tools

# 连接建立后的回调类型
StreamHandleCallback = Callable[[StreamHandle], Awaitable[None]]


class OllamaHttpClient:
    """Ollama OpenAI 兼容 Chat Completions 客户端。"""

    def __init__(self, settings: Settings) -> None:
        """保存 ``Settings``，请求时再读其中的 base_url、key、模型等。"""
        self._settings = settings

    def _chat_headers(self) -> dict[str, str]:
        """构造 Chat Completions 请求头。

        仅当显式配置了 LLM_API_KEY 时才添加 Bearer 认证头，
        本地 Ollama 通常不需要认证。
        """
        headers: dict[str, str] = {"Content-Type": "application/json"}
        api_key = self._settings.get("LLM_API_KEY", "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _build_chat_payload(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None,
        stream: bool = False,
        tools: list[dict] | None = None,
    ) -> dict[str, Any]:
        """组装请求 JSON：模型、messages、可选 stream / 采样参数 / 工具定义。

        注意：不包含 enable_thinking（Ollama 不支持此 DeepSeek 私有参数）。
        """
        payload: dict[str, Any] = {
            "model": self._settings.get("LLM_MODEL", "llama3"),
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
        if tools:
            payload["tools"] = to_openai_tools(tools)
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
        """同步调用上游，解析 ``choices[0].message.content`` 为完整字符串。"""
        url = f'{self._settings.get("LLM_BASE_URL", "http://localhost:11434")}/v1/chat/completions'
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
        """非流式调用上游，返回 content blocks 列表（含 text + thinking）。"""
        url = f'{self._settings.get("LLM_BASE_URL", "http://localhost:11434")}/v1/chat/completions'
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
        # Ollama 用 "reasoning"，DeepSeek 用 "reasoning_content"
        reasoning_text = (message.get("reasoning") or message.get("reasoning_content") or "").strip()

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
        """流式调用上游，解析 SSE ``data:`` 行，逐段 yield ``(kind, data)``。

        kind 取值同 ``StreamHandle.receive()``。
        使用 ``StreamHandle`` 独立管理连接生命周期，不跨 task 操作。

        参数:
            on_connect: 连接建立后的回调，接收 ``StreamHandle`` 供注册到中断注册表。
        """
        url = f'{self._settings.get("LLM_BASE_URL", "http://localhost:11434")}/v1/chat/completions'
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
        # 将 OpenAI 协议的字段名映射为内部统一命名
        # Ollama 使用 "reasoning"，DeepSeek 使用 "reasoning_content"
        _KIND_MAP = {"content": "text", "reasoning_content": "thinking", "reasoning": "thinking"}
        async for kind, data in handle.receive():
            yield (_KIND_MAP.get(kind, kind), data)
