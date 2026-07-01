"""OpenAI Chat Completions 格式转换：统一内部格式 ↔ OpenAI API 格式。

被 `DeepSeekHttpClient` 和 `OllamaHttpClient` 共用。
"""

from __future__ import annotations

import json
from typing import Any

from lumen_agent.domain.messages import ensure_blocks


def _is_sendable_image_url(url: str) -> bool:
    """判断图像 URL 是否可以直接发给外部 LLM。

    本地文件引用（以 "/" 开头的相对路径，如 /v1/files/xxx）仅用于 DB 存储，
    不能发给外部 LLM。data URI 和 http(s):// 可以发送。
    """
    return url.startswith(("http://", "https://", "data:"))


def to_openai_tools(internal_tools: list[dict]) -> list[dict]:
    """将统一内部格式工具定义转为 OpenAI Chat Completions 格式。

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


def to_openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """将内部消息格式转换为 OpenAI Chat Completions API 格式。

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
        # 回复增量
        text_parts: list[str] = []
        # 思考增量
        thinking_parts: list[str] = []
        # 工具调用
        tool_use_blocks: list[dict] = []
        # 工具调用结果
        tool_result_blocks: list[dict] = []

        for block in content:
            btype = block.get("type", "")
            if btype == "text":
                text_parts.append(block.get("text", ""))
            elif btype == "thinking":
                # 多轮时必须把上一轮 reasoning_content 原样带回
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
                # 嵌入在 assistant 内部的 tool_result → 转译为 role:tool API 消息
                for tr in tool_result_blocks:
                    result.append(
                        {
                            "role": "tool",
                            "tool_call_id": tr["tool_use_id"],
                            "content": tr.get("content", ""),
                        }
                    )
            else:
                asst: dict[str, Any] = {"role": "assistant", "content": "".join(text_parts)}
                if combined_thinking:
                    asst["reasoning_content"] = combined_thinking
                result.append(asst)
                # 即使没有 tool_use，也可能有嵌入的 tool_result（纯结果场景）
                for tr in tool_result_blocks:
                    result.append(
                        {
                            "role": "tool",
                            "tool_call_id": tr["tool_use_id"],
                            "content": tr.get("content", ""),
                        }
                    )

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
                # 收集图像块，过滤掉本地文件引用（以 "/" 开头的相对路径）
                # 这类引用是 DB 存储格式，不能直接发给外部 LLM
                # 真正要送给 LLM 的图像（data URI 或 https://）来自 user_extra_blocks
                image_blocks = [
                    b for b in content
                    if b.get("type") == "image_url"
                    and _is_sendable_image_url(b.get("image_url", {}).get("url", ""))
                ]
                if image_blocks:
                    # 有可发送图像时输出多模态数组
                    multimodal: list[dict] = []
                    combined_text = "".join(text_parts)
                    if combined_text:
                        multimodal.append({"type": "text", "text": combined_text})
                    for ib in image_blocks:
                        multimodal.append({
                            "type": "image_url",
                            "image_url": ib.get("image_url", {}),
                        })
                    result.append({"role": "user", "content": multimodal})
                else:
                    result.append({"role": "user", "content": "".join(text_parts)})

        else:
            # system 等其他角色
            result.append({"role": role, "content": "".join(text_parts)})

    return result
