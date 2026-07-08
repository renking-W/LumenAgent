"""统一内部消息格式与序列化辅助。"""

from __future__ import annotations

import json
from typing import Any, TypedDict, cast


class ContentBlock(TypedDict, total=False):
    """统一内容块：text / thinking / tool_use / tool_result / image_url。"""

    type: str
    text: str
    thinking: str
    id: str
    name: str
    input: dict[str, Any]
    tool_use_id: str
    content: str
    is_error: bool
    # 图像块：{"url": "https://..." 或 "data:image/...;base64,..."}
    image_url: dict[str, str]


class InternalMessage(TypedDict):
    """内部消息结构：role + content blocks。"""

    role: str
    content: list[ContentBlock]


def text_message(role: str, text: str) -> InternalMessage:
    """构造单条纯文本内部消息。"""
    return {"role": role, "content": [{"type": "text", "text": text}]}


def image_block(url: str) -> ContentBlock:
    """构造图像内容块（url 可为 https:// 或 data URI）。"""
    return {"type": "image_url", "image_url": {"url": url}}


def _parse_blocks(content: Any) -> list[ContentBlock]:
    """将各类 content 形态解析为 block 列表（不做 tool_result 关联修复）。"""
    if content is None:
        return []
    if isinstance(content, list):
        return cast(
            list[ContentBlock],
            cast(object, [block for block in content if isinstance(block, dict)]),
        )
    if isinstance(content, str):
        raw = content.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return [{"type": "text", "text": content}]
        if isinstance(parsed, list):
            return cast(
                list[ContentBlock],
                cast(object, [block for block in parsed if isinstance(block, dict)]),
            )
        return [{"type": "text", "text": content}]
    return [{"type": "text", "text": str(content)}]


def link_tool_result_ids(blocks: list[ContentBlock]) -> list[ContentBlock]:
    """入库前补齐 tool_result.tool_use_id（同条消息内向前匹配 tool_use.id）。"""
    result: list[ContentBlock] = []
    last_tool_use_id: str | None = None
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block = dict(block)
        btype = block.get("type")
        if btype == "tool_use":
            tid = block.get("id")
            if isinstance(tid, str) and tid:
                last_tool_use_id = tid
        elif btype == "tool_result":
            tid = block.get("tool_use_id")
            if (not tid or not str(tid).strip()) and last_tool_use_id:
                block["tool_use_id"] = last_tool_use_id
            content = block.get("content")
            if isinstance(content, list):
                block["content"] = json.dumps(content, ensure_ascii=False)
        result.append(cast(ContentBlock, cast(object, block)))
    return result


def ensure_blocks(content: Any) -> list[ContentBlock]:
    """将 content 解析为 block 列表（字符串 / JSON 字符串兼容）。"""
    return _parse_blocks(content)


def blocks_to_json(blocks: list[ContentBlock]) -> str:
    """将内容块列表序列化为 JSON 字符串。"""
    return json.dumps(blocks, ensure_ascii=False)


def normalize_content_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """将前端的 ContentBlock 列表转换为内部存储兼容的格式。"""
    result: list[dict[str, Any]] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block = dict(block)
        if block.get("type") == "tool_result":
            content = block.get("content")
            if isinstance(content, list):
                block["content"] = json.dumps(content, ensure_ascii=False)
        result.append(block)
    return result