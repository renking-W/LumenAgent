"""记忆文件路由：纯 HTTP 编排，全部业务逻辑委托给 memory_file_service。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from lumen_agent.api.schemas.memory_dtos import MemoryFileItem
from lumen_agent.application.service.memory_file_service import (
    list_memory_files as svc_list_memories,
    reindex_memory_files as svc_reindex_memories,
)
from lumen_agent.config import Settings, get_settings

router = APIRouter(prefix="/v1/memories", tags=["memories"])


@router.get("", response_model=list[MemoryFileItem])
async def list_memories() -> list[MemoryFileItem]:
    return svc_list_memories()


@router.post("/reindex")
async def reindex_memories(settings: Settings = Depends(get_settings)) -> dict:
    return await svc_reindex_memories(settings)
