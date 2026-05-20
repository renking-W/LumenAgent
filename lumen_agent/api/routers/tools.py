"""工具列表路由：GET /v1/tools。"""

from __future__ import annotations

from fastapi import APIRouter

from lumen_agent.agent.tools import init_tools
from lumen_agent.agent.tools.registry import ToolRegistry
from lumen_agent.api.schemas.capability_dtos import ToolInfo

router = APIRouter(prefix="/v1", tags=["capabilities"])


@router.get("/tools", response_model=list[ToolInfo])
async def list_tools() -> list[ToolInfo]:
    """返回当前 Agent 已注册的所有工具（name、description、parameters）。"""
    init_tools()
    return [
        ToolInfo(
            name=t.name,
            description=t.description,
            parameters=t.parameters,
        )
        for t in ToolRegistry.create_all_tools()
    ]
