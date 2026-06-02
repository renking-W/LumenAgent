"""统一内部消息格式与序列化辅助。"""

from __future__ import annotations

import json
from typing import Any, TypedDict


class ContentBlock(TypedDict, total=False):
    """统一内容块：当前先支持 text / thinking / tool_use / tool_result。"""

    type: str
    text: str
    thinking: str
    id: str
    name: str
    input: dict[str, Any]
    tool_use_id: str
    content: str
    is_error: bool


class InternalMessage(TypedDict):
    """内部消息结构：role + content blocks。"""

    role: str
    content: list[ContentBlock]


def text_message(role: str, text: str) -> InternalMessage:
    """构造单条纯文本内部消息。"""
    return {"role": role, "content": [{"type": "text", "text": text}]}


def ensure_blocks(content: Any) -> list[ContentBlock]:
    """兼容旧数据：字符串会被包装成 text block；JSON 字符串会反序列化。"""
    if content is None:
        return []
    if isinstance(content, list):
        return [block for block in content if isinstance(block, dict)]
    if isinstance(content, str):
        raw = content.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return [{"type": "text", "text": content}]
        if isinstance(parsed, list):
            return [block for block in parsed if isinstance(block, dict)]
        return [{"type": "text", "text": content}]
    return [{"type": "text", "text": str(content)}]


def blocks_to_json(blocks: list[ContentBlock]) -> str:
    """将内容块列表序列化为 JSON 字符串。"""
    return json.dumps(blocks, ensure_ascii=False)


def normalize_content_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """将前端的 ContentBlock 列表转换为内部存储兼容的格式。

    主要处理：
    - ``tool_result``：Anthropic API 中 content 为 ``list[ContentBlock]``，
      内部存储需要转为 JSON 字符串。
    """
    result: list[dict[str, Any]] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block = dict(block)  # 防御性拷贝
        if block.get("type") == "tool_result":
            content = block.get("content")
            if isinstance(content, list):
                block["content"] = json.dumps(content, ensure_ascii=False)
        result.append(block)
    return result