"""工具注册表：全局唯一的 name → class 映射，工具实例按需创建。"""

from __future__ import annotations

from lumen_agent.agent.tools.base import BaseTool


class ToolRegistry:
    """
    工具注册表（类变量，进程全局唯一）。

    注册表本身存储 name → class 映射，在 import 时通过 @register 装饰器写入一次。
    工具实例由 create_all_tools() 按需创建，每次调用返回新实例，session 间互不干扰。
    """

    _tools: dict[str, type[BaseTool]] = {}

    @classmethod
    def register(cls, tool_cls: type[BaseTool]) -> type[BaseTool]:
        """装饰器：将工具类注册到注册表。在模块 import 时自动执行。"""
        cls._tools[tool_cls.name] = tool_cls
        return tool_cls

    @classmethod
    def create_tool(cls, name: str) -> BaseTool | None:
        """按名称实例化工具；不存在返回 None。"""
        tool_cls = cls._tools.get(name)
        return tool_cls() if tool_cls else None

    @classmethod
    def create_all_tools(cls) -> list[BaseTool]:
        """实例化所有已注册工具，返回新实例列表。"""
        return [tool_cls() for tool_cls in cls._tools.values()]

    @classmethod
    def list_internal_schemas(cls) -> list[dict]:
        """返回统一内部格式的工具定义列表，供适配器转换为厂商格式。"""
        return [tool_cls().to_internal_schema() for tool_cls in cls._tools.values()]

    @classmethod
    def clear(cls) -> None:
        """清空注册表（主要用于测试隔离）。"""
        cls._tools.clear()
