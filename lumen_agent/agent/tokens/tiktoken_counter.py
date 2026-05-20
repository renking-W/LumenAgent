"""基于 tiktoken 的 token 计数实现（适用于 DeepSeek / OpenAI cl100k_base 编码）。"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# 每条消息固定格式开销（role 包装等），参考 OpenAI cookbook
_MSG_OVERHEAD = 3
_REPLY_OVERHEAD = 3  # 整个 reply 额外 3 token


def _get_encoding(encoding_name: str):
    """获取 tiktoken 编码器；首次调用后缓存在模块变量中。"""
    import tiktoken
    return tiktoken.get_encoding(encoding_name)


class TiktokenCounter:
    """使用 tiktoken 对文本和 messages 进行 token 计数。

    encoding_name: 默认 "cl100k_base"（DeepSeek / GPT-4 / GPT-3.5 共用）。
    """

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        self._encoding_name = encoding_name
        self._enc = None

    def _get_enc(self):
        if self._enc is None:
            self._enc = _get_encoding(self._encoding_name)
        return self._enc

    def count(self, text: str) -> int:
        """计算单段文本的 token 数。"""
        if not text:
            return 0
        try:
            return len(self._get_enc().encode(text))
        except Exception as exc:
            logger.warning("tiktoken count failed, falling back to char estimate: %s", exc)
            return _char_estimate(text)

    def count_messages(self, messages: list[dict[str, Any]]) -> int:
        """估算完整 messages 列表的 token 数。

        覆盖范围：
        - 每条消息 role 标签 + 3 token 格式开销
        - text / thinking block
        - tool_use block：name + id + json(input)
        - tool_result block：content 文本
        - system 消息的 string content
        """
        total = _REPLY_OVERHEAD
        for msg in messages:
            total += _MSG_OVERHEAD
            content = msg.get("content", [])
            if isinstance(content, str):
                total += self.count(content)
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type", "")
                    if btype == "text":
                        total += self.count(block.get("text") or "")
                    elif btype == "thinking":
                        total += self.count(block.get("thinking") or "")
                    elif btype == "tool_use":
                        total += self.count(block.get("name") or "")
                        total += self.count(block.get("id") or "")
                        inp = block.get("input")
                        if inp:
                            total += self.count(
                                inp if isinstance(inp, str) else json.dumps(inp, ensure_ascii=False)
                            )
                    elif btype == "tool_result":
                        total += self.count(block.get("content") or "")
        return total


def _char_estimate(text: str) -> int:
    """简单字符估算（tiktoken 失败时的兜底）。"""
    cn = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    return cn + (len(text) - cn) // 4 + 1
