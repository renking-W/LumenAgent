"""零依赖字符估算 TokenCounter（tiktoken 不可用时的兜底实现）。

中文字符按 1:1 计，ASCII 字符按 4:1 计（经验近似）。
误差约 20–30%，建议仅作兜底而非主路径。
"""

from __future__ import annotations

import json
from typing import Any

_MSG_OVERHEAD = 3
_REPLY_OVERHEAD = 3


def _estimate(text: str) -> int:
    if not text:
        return 0
    cn = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    ascii_part = len(text) - cn
    return cn + ascii_part // 4 + 1


class CharCounter:
    """字符加权估算，不依赖任何外部包。"""

    def count(self, text: str) -> int:
        return _estimate(text)

    def count_messages(self, messages: list[dict[str, Any]]) -> int:
        total = _REPLY_OVERHEAD
        for msg in messages:
            total += _MSG_OVERHEAD
            content = msg.get("content", [])
            if isinstance(content, str):
                total += _estimate(content)
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type", "")
                    if btype == "text":
                        total += _estimate(block.get("text") or "")
                    elif btype == "thinking":
                        total += _estimate(block.get("thinking") or "")
                    elif btype == "tool_use":
                        total += _estimate(block.get("name") or "")
                        total += _estimate(block.get("id") or "")
                        inp = block.get("input")
                        if inp:
                            total += _estimate(
                                inp if isinstance(inp, str) else json.dumps(inp, ensure_ascii=False)
                            )
                    elif btype == "tool_result":
                        total += _estimate(block.get("content") or "")
        return total
