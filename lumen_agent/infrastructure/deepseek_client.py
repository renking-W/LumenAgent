"""DeepSeek OpenAI 兼容 `POST /v1/chat/completions`；HTTP 错误映射在路由层。"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from lumen_agent.config import Settings
from lumen_agent.domain.messages import ensure_blocks


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

        timeout = httpx.Timeout(120.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
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

        kind 取值：
          "content"           – 文本增量（str）
          "reasoning_content" – 思维链增量（str）
          "tool_use"          – 工具调用块（dict，仅当传入 tools 时）
        """
        url = f"{self._settings.deepseek_base_url}/v1/chat/completions"
        headers = self._chat_headers()
        api_messages = _to_openai_messages(messages)
        payload = self._build_chat_payload(
            api_messages, temperature=temperature, stream=True, tools=tools
        )

        # 按 index 累积工具调用的 arguments 片段
        # {index: {id, name, arguments}}
        pending_tool_calls: dict[int, dict[str, str]] = {}
        finish_reason: str | None = None

        timeout = httpx.Timeout(120.0, connect=10.0)
        # 异步发http请求
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    try:
                        detail = body.decode("utf-8", errors="replace")[:4000]
                    except Exception:
                        detail = repr(body)
                    raise RuntimeError(
                        f"upstream HTTP {response.status_code} on chat/completions: {detail}"
                    )
                response.raise_for_status()
                # 获取大模型返回数据（异步获取）
                async for line in response.aiter_lines():
                    # 去除首尾空白
                    line = line.strip()
                    if not line or line.startswith(":"):
                        continue
                    # 去除非数据行
                    if not line.startswith("data:"):
                        continue
                    # 获取返回具体数据
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        obj: dict[str, Any] = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    # 有error数据直接中断
                    err = obj.get("error")
                    if err is not None:
                        msg = (
                            err.get("message") or json.dumps(err, ensure_ascii=False)
                            if isinstance(err, dict)
                            else str(err)
                        )
                        raise RuntimeError(msg)

                    choices = obj.get("choices") or []
                    if not choices:
                        continue

                    choice = choices[0] or {}
                    finish_reason = choice.get("finish_reason") or finish_reason
                    delta: dict[str, Any] = choice.get("delta") or {}

                    # 普通文本 / 思维链
                    for field in ("reasoning_content", "content"):
                        piece = delta.get(field)
                        if isinstance(piece, str) and piece:
                            yield (field, piece)

                    # 工具调用 delta 累积
                    tc_deltas: list[dict] = delta.get("tool_calls") or []
                    for tc_delta in tc_deltas:
                        idx: int = tc_delta.get("index", 0)
                        if idx not in pending_tool_calls:
                            pending_tool_calls[idx] = {
                                "id": tc_delta.get("id", ""),
                                "name": (tc_delta.get("function") or {}).get("name", ""),
                                "arguments": "",
                            }
                        args_piece = (tc_delta.get("function") or {}).get("arguments", "")
                        if args_piece:
                            pending_tool_calls[idx]["arguments"] += args_piece

        # 流结束后，若有累积的工具调用则一次性 yield
        if pending_tool_calls:
            for tc in pending_tool_calls.values():
                try:
                    parsed_input = json.loads(tc["arguments"]) if tc["arguments"] else {}
                except json.JSONDecodeError:
                    parsed_input = {"_raw": tc["arguments"]}
                yield (
                    "tool_use",
                    {
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": parsed_input,
                    },
                )
