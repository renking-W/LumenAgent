"""DeepSeek OpenAI 兼容 `POST /v1/chat/completions`；HTTP 错误映射在路由层。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from lumen_agent.config import Settings
from lumen_agent.domain.messages import ensure_blocks
from lumen_agent.infrastructure.http_pool import get_http_pool



def _to_openai_tools(internal_tools: list[dict]) -> list[dict]:
    """将统一内部格式工具定义转为 OpenAI/DeepSeek 格式。

    内部格式: {name, description, input_schema}
    OpenAI 格式: {type: "function", function: {name, description, parameters}}
    """
    result = []
    for t in internal_tools:
        result.append(
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
        )
    return result


def _to_openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """将内部消息格式转换为 OpenAI/DeepSeek API 格式。

    内部格式: {role, content: list[ContentBlock]}
    OpenAI 格式: {role, content: str} 或 tool_calls / tool 消息
    """
    result: list[dict[str, Any]] = []
    for msg in messages:
        role: str = msg["role"]
        raw_content = msg.get("content", [])
        # 与仓储/历史一致：块列表，或 SQLite 里存的内容块 JSON 字符串
        if isinstance(raw_content, list):
            content: list[Any] = [b for b in raw_content if isinstance(b, dict)]
        else:
            content = ensure_blocks(raw_content)
        text_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_use_blocks: list[dict] = []
        tool_result_blocks: list[dict] = []

        for block in content:
            btype = block.get("type", "")
            if btype == "text":
                text_parts.append(block.get("text", ""))
            elif btype == "thinking":
                # DeepSeek 思维链模式：多轮时必须把上一轮 reasoning_content 原样带回
                thinking_parts.append(block.get("thinking", "") or "")
            elif btype == "tool_use":
                tool_use_blocks.append(block)
            elif btype == "tool_result":
                tool_result_blocks.append(block)

        combined_thinking = "".join(thinking_parts).strip()

        if role == "assistant":
            if tool_use_blocks:
                # assistant 消息带工具调用
                api_msg = {"role": "assistant"}
                combined_text = "".join(text_parts).strip()
                if combined_text:
                    api_msg["content"] = combined_text
                else:
                    # 部分网关对 null 不兼容；纯 tool_calls 时用空串
                    api_msg["content"] = ""
                if combined_thinking:
                    api_msg["reasoning_content"] = combined_thinking
                api_msg["tool_calls"] = [
                    {
                        "id": tb["id"],
                        "type": "function",
                        "function": {
                            "name": tb["name"],
                            "arguments": json.dumps(tb.get("input", {}), ensure_ascii=False),
                        },
                    }
                    for tb in tool_use_blocks
                ]
                result.append(api_msg)
            else:
                asst: dict[str, Any] = {"role": "assistant", "content": "".join(text_parts)}
                if combined_thinking:
                    asst["reasoning_content"] = combined_thinking
                result.append(asst)

        elif role == "user":
            if tool_result_blocks:
                # tool_result 块转为 role=tool 消息（OpenAI Function Calling 格式）
                for tr in tool_result_blocks:
                    result.append(
                        {
                            "role": "tool",
                            "tool_call_id": tr["tool_use_id"],
                            "content": tr.get("content", ""),
                        }
                    )
                # 若同时有文本（罕见），追加为普通 user 消息
                plain = "".join(text_parts).strip()
                if plain:
                    result.append({"role": "user", "content": plain})
            else:
                result.append({"role": "user", "content": "".join(text_parts)})

        else:
            # system 等其他角色
            result.append({"role": role, "content": "".join(text_parts)})

    return result


class DeepSeekHttpClient:
    """DeepSeek OpenAI 兼容 Chat Completions 客户端。"""

    def __init__(self, settings: Settings) -> None:
        """保存 ``Settings``，请求时再读其中的 base_url、key、模型等。"""
        self._settings = settings

    def _chat_headers(self) -> dict[str, str]:
        """构造 Chat Completions 请求头（Bearer + JSON）。"""
        return {
            "Authorization": f"Bearer {self._settings.deepseek_api_key}",
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
        """组装请求 JSON：模型、messages、可选 stream / 采样参数 / 工具定义。"""
        payload: dict[str, Any] = {
            "model": self._settings.deepseek_model,
            "messages": messages,
        }
        if stream:
            payload["stream"] = True
        effective_temperature = (
            temperature if temperature is not None else self._settings.deepseek_temperature
        )
        if effective_temperature is not None:
            payload["temperature"] = effective_temperature
        if self._settings.deepseek_max_tokens is not None:
            payload["max_tokens"] = self._settings.deepseek_max_tokens
        if self._settings.deepseek_top_p is not None:
            payload["top_p"] = self._settings.deepseek_top_p
        if self._settings.deepseek_enable_thinking is not None:
            payload["enable_thinking"] = self._settings.deepseek_enable_thinking
        if tools:
            payload["tools"] = _to_openai_tools(tools)
            payload["tool_choice"] = "auto"
        return payload

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
    ) -> str:
        """同步调用上游，解析 ``choices[0].message.content`` 为完整字符串。"""
        url = f"{self._settings.deepseek_base_url}/v1/chat/completions"
        headers = self._chat_headers()
        api_messages = _to_openai_messages(messages)
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

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
        tools: list[dict] | None = None,
    ) -> AsyncIterator[tuple[str, str | dict]]:
        """流式调用上游，解析 SSE ``data:`` 行，逐段 yield ``(kind, data)``。

        kind 取值同 ``StreamHandle.receive()``。
        使用 ``StreamHandle`` 独立管理连接生命周期，不跨 task 操作。
        """
        url = f"{self._settings.deepseek_base_url}/v1/chat/completions"
        headers = self._chat_headers()
        api_messages = _to_openai_messages(messages)
        payload = self._build_chat_payload(
            api_messages, temperature=temperature, stream=True, tools=tools
        )

        pool = get_http_pool()
        handle = pool.send_stream("POST", url, headers=headers, json=payload)
        await handle.connect()
        async for kind, data in handle.receive():
            yield (kind, data)
