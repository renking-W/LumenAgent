"""Sub-Agent 适配器注册表。

用法：
    from lumen_agent.sub_agents.registry import SubAgentRegistry

    # 列出所有已注册的适配器（含可用性检测）
    adapters = SubAgentRegistry.list_available()

    # 按名称获取适配器实例
    adapter = SubAgentRegistry.get("claude_code")
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lumen_agent.sub_agents.base import AcpAgentAdapter

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, "AcpAgentAdapter"] = {}


class SubAgentRegistry:
    """全局适配器注册表（类-level 单例）。"""

    @classmethod
    def register(cls, adapter_cls: type["AcpAgentAdapter"]) -> type["AcpAgentAdapter"]:
        """装饰器：注册一个适配器类到全局表中。"""
        instance = adapter_cls()
        _REGISTRY[instance.name] = instance
        logger.debug("SubAgentRegistry 注册适配器: %s", instance.name)
        return adapter_cls

    @classmethod
    def get(cls, name: str) -> "AcpAgentAdapter | None":
        """按名称获取适配器实例。"""
        _ensure_loaded()
        return _REGISTRY.get(name)

    @classmethod
    def list_all(cls) -> list[dict]:
        """列出所有已注册适配器（含基础信息，不含可用性检测）。"""
        _ensure_loaded()
        return [
            {"name": a.name, "label": a.label}
            for a in _REGISTRY.values()
        ]

    @classmethod
    def list_available(cls) -> list[dict]:
        """列出所有适配器并附带可用性检测结果。"""
        _ensure_loaded()
        result = []
        for a in _REGISTRY.values():
            available = False
            hint = ""
            try:
                available = a.is_available()
                if not available:
                    hint = a.availability_hint()
            except Exception as exc:
                logger.warning("适配器 %s 可用性检测异常: %s", a.name, exc)
                hint = str(exc)
            result.append({
                "name": a.name,
                "label": a.label,
                "available": available,
                "hint": hint,
            })
        return result


def _ensure_loaded() -> None:
    """确保所有内置适配器已被导入（触发 @register 装饰器）。"""
    if _REGISTRY:
        return
    try:
        import lumen_agent.sub_agents.claude_code  # noqa: F401
        import lumen_agent.sub_agents.cursor_agent  # noqa: F401
        import lumen_agent.sub_agents.codex  # noqa: F401
    except ImportError:
        pass
