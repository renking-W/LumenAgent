"""配置管理路由：纯 HTTP 编排，全部业务逻辑委托给 config_service。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from lumen_agent.api.schemas.config_dtos import (
    ConfigListResponse,
    UpdateConfigRequest,
    UpdateConfigResponse,
)
from lumen_agent.application.service.common.config_service import (
    list_configs as svc_list_configs,
    update_config as svc_update_config,
)

router = APIRouter(prefix="/v1/configs", tags=["config"])


@router.get("", response_model=ConfigListResponse)
async def list_configs() -> ConfigListResponse:
    return svc_list_configs()


@router.post("", response_model=UpdateConfigResponse, status_code=status.HTTP_201_CREATED)
async def update_config(body: UpdateConfigRequest) -> UpdateConfigResponse:
    key = body.key.strip().upper()
    value = body.value.strip()
    try:
        return svc_update_config(key, value)
    except ValueError as e:
        detail = str(e)
        if "系统保护" in detail:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
        raise HTTPException(status_code=422, detail=detail)
