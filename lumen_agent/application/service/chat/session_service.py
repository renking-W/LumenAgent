"""会话服务：消息内容标准化等非 HTTP 编排逻辑。"""

from __future__ import annotations

from typing import Any

from lumen_agent.domain.messages import normalize_content_blocks, text_message


def normalize_and_prepare_content(
    role: str,
    content: str | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """将原始消息内容转换为用于持久化的标准化内容块列表。

    - 字符串 → 包装为 text_message block → normalize
    - list[dict] → 直接 normalize（兼容前端已组装好的块）
    """
    if isinstance(content, list):
        return normalize_content_blocks(content)
    return normalize_content_blocks(text_message(role, content)["content"])
