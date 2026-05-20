"""Token 计数子包：可插拔接口 + 按模型分发的工厂函数。

当前路由规则：
  - "deepseek-*" 系列 → TiktokenCounter("cl100k_base")
  - 其他 / 未知        → TiktokenCounter("cl100k_base")（兜底，tiktoken 安装后通用）
  - tiktoken 不可用时   → CharCounter（零依赖估算）

新增模型时，在 get_token_counter() 的分发表里追加一行即可。
"""

from __future__ import annotations

import logging

from lumen_agent.agent.tokens.meta import TokenCounter
from lumen_agent.agent.tokens.char_counter import CharCounter

logger = logging.getLogger(__name__)

# 模块级单例缓存，避免每次请求重建编码器
_counter_cache: dict[str, TokenCounter] = {}


def get_token_counter(model_name: str) -> TokenCounter:
    """根据模型名返回对应的 TokenCounter 实例（带缓存）。

    扩展方式：在下方 _ROUTING 字典里添加 (model_prefix, encoding_name) 映射。
    """
    if model_name in _counter_cache:
        return _counter_cache[model_name]

    counter = _build_counter(model_name)
    _counter_cache[model_name] = counter
    return counter


def _build_counter(model_name: str) -> TokenCounter:
    """按模型名构建 TokenCounter，tiktoken 不可用时降级到 CharCounter。"""
    # 路由表：(model_name_prefix, tiktoken_encoding)
    _ROUTING: list[tuple[str, str]] = [
        ("deepseek", "cl100k_base"),
        ("gpt-4", "cl100k_base"),
        ("gpt-3.5", "cl100k_base"),
    ]

    encoding_name = "cl100k_base"  # 默认
    for prefix, enc in _ROUTING:
        if model_name.lower().startswith(prefix):
            encoding_name = enc
            break

    try:
        from lumen_agent.agent.tokens.tiktoken_counter import TiktokenCounter
        counter = TiktokenCounter(encoding_name)
        # 预热：验证 tiktoken 可用
        counter.count("test")
        return counter
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "tiktoken unavailable (%s), falling back to CharCounter for model '%s'",
            exc, model_name,
        )
        return CharCounter()


__all__ = ["TokenCounter", "CharCounter", "get_token_counter"]
