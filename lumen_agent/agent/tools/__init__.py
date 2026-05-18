"""工具子包：import 触发装饰器注册；预留 init_tools() 供条件注册扩展。"""

from __future__ import annotations

from lumen_agent.agent.tools.base import BaseTool, ToolResult
from lumen_agent.agent.tools.registry import ToolRegistry
from lumen_agent.agent.tools.read import Read  # noqa: F401 – 触发 @ToolRegistry.register

__all__ = ["BaseTool", "ToolResult", "ToolRegistry", "Read"]


def init_tools() -> None:
    """条件注册可选工具（如需 API key 的 web_search 等），在应用启动时调用。"""
    # 预留：后续工具在此处按条件注册
