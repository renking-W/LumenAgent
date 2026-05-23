"""工具子包：import 触发装饰器注册；预留 init_tools() 供条件注册扩展。"""

from __future__ import annotations

from lumen_agent.agent.tools.base import BaseTool, ToolResult
from lumen_agent.agent.tools.registry import ToolRegistry
from lumen_agent.agent.tools.read import Read  # noqa: F401 – 触发 @ToolRegistry.register
from lumen_agent.agent.tools.write import Write  # noqa: F401
from lumen_agent.agent.tools.bash import Bash  # noqa: F401
from lumen_agent.agent.tools.web_search import WebSearch  # noqa: F401
from lumen_agent.agent.tools.web_fetch import WebFetch  # noqa: F401
from lumen_agent.agent.tools.knowledge import KnowledgeSearch, KnowledgeInsert  # noqa: F401

__all__ = ["BaseTool", "ToolResult", "ToolRegistry", "Read", "Write", "Bash", "WebSearch", "WebFetch", "KnowledgeSearch", "KnowledgeInsert"]


def init_tools() -> None:
    """条件注册可选工具，在应用启动时调用。"""
    # 当前知识工具通过 import 时的装饰器注册，后续如需条件启用可放到这里。