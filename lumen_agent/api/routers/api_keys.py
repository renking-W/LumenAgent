"""API Key 管理路由：创建 / 列表 / 删除 / 启停。"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from lumen_agent.api.dependency import get_settings, verify_api_key
from lumen_agent.api.schemas.api_key_dtos import (
    ApiKeyCreateRequest,
    ApiKeyCreatedResponse,
    ApiKeyListResponse,
    ApiKeyResponse,
    ApiKeyToggleRequest,
)
from lumen_agent.application.service.api_key_service import generate_api_key
from lumen_agent.config import Settings, resolve_db_path
from lumen_agent.infrastructure.data_base.sqlite_api_key import (
    SqliteApiKeyRepository,
)

_logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/api-keys",
    tags=["api-keys"],
)


def _get_repo(settings: Settings = Depends(get_settings)) -> SqliteApiKeyRepository:
    return SqliteApiKeyRepository(resolve_db_path(settings))


@router.post("", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreateRequest,
    settings: Settings = Depends(get_settings),
) -> ApiKeyCreatedResponse:
    """创建一个新的 API Key。原始 Key 仅在本次响应中返回。"""
    repo = _get_repo(settings)
    raw_key, key_hash = generate_api_key()
    meta = await repo.create(key_hash, name=body.name)
    _logger.info("API Key 已创建: id=%s name=%s", meta["id"], body.name or "(未命名)")
    return ApiKeyCreatedResponse(
        id=meta["id"],
        name=meta["name"],
        enabled=meta["enabled"],
        created_at=meta["created_at"],
        updated_at=meta["updated_at"],
        key=raw_key,
    )


@router.get("", response_model=ApiKeyListResponse)
async def list_api_keys(
    settings: Settings = Depends(get_settings),
) -> ApiKeyListResponse:
    """列出所有 API Key 的元信息（不含原始 Key）。"""
    repo = _get_repo(settings)
    keys = await repo.list_all()
    return ApiKeyListResponse(
        total=len(keys),
        keys=[ApiKeyResponse(**k) for k in keys],
    )


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: Annotated[str, Path(min_length=1)],
    settings: Settings = Depends(get_settings),
) -> dict:
    """删除指定的 API Key。"""
    repo = _get_repo(settings)
    deleted = await repo.delete(key_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="API Key 不存在")
    _logger.info("API Key 已删除: id=%s", key_id)
    return {"status": "deleted", "key_id": key_id}


@router.patch("/{key_id}", response_model=ApiKeyResponse)
async def toggle_api_key(
    key_id: Annotated[str, Path(min_length=1)],
    body: ApiKeyToggleRequest,
    settings: Settings = Depends(get_settings),
) -> ApiKeyResponse:
    """启用或禁用指定的 API Key。"""
    repo = _get_repo(settings)
    ok = await repo.set_enabled(key_id, body.enabled)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="API Key 不存在")
    record = await repo.get(key_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="API Key 不存在")
    _logger.info("API Key 已%s: id=%s", "启用" if body.enabled else "禁用", key_id)
    return ApiKeyResponse(**record)
