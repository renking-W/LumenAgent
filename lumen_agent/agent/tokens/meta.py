"""TokenCounter 接口定义（Protocol，不依赖具体实现）。"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TokenCounter(Protocol):
    """可插拔的 token 计数接口。

    实现类需提供两个方法：
    - count(text)         → 单段文本的 token 数
    - count_messages(...) → 完整 messages 列表的估算 token 数
    """

    def count(self, text: str) -> int:
        """计算单段文本的 token 数。"""
        ...

    def count_messages(self, messages: list[dict[str, Any]]) -> int:
        """估算 LLM 输入 messages 列表的总 token 数。

        应覆盖：role 标签、text / thinking / tool_use(name+id+input) /
        tool_result(content) 等全部文本，以及每条消息约 3 token 的格式开销。
        """
        ...
