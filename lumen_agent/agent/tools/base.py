"""工具基础类：ToolResult + BaseTool。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """工具执行结果（模型无关）。"""

    status: str          # "success" | "error"
    result: Any          # 执行结果（字符串或结构化数据）
    execution_time: float = field(default=0.0)
    is_error: bool = field(default=False)

    @staticmethod
    def success(result: Any) -> "ToolResult":
        return ToolResult(status="success", result=result)

    @staticmethod
    def error(message: str) -> "ToolResult":
        return ToolResult(status="error", result=message, is_error=True)


class BaseTool(ABC):
    """
    所有工具的基类。

    子类只需定义 name / description / parameters 三个类属性并实现 execute()。
    parameters 采用 JSON Schema 格式（与模型无关的统一内部格式）。
    """

    name: str = ""
    description: str = ""
    parameters: dict = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    @abstractmethod
    async def execute(self, params: dict) -> ToolResult:
        """子类实现具体逻辑。异步以便处理 IO 密集型操作。"""

    def to_internal_schema(self) -> dict:
        """转换为统一内部格式的工具定义，供 ModelAdapter 转为各厂商格式。"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }
