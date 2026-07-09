"""VM 管理路由：虚拟机配置、SSH 连接、流式命令执行与日志查看。"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import StreamingResponse

from lumen_agent.api.dependency import verify_api_key
from lumen_agent.api.schemas.vm_dtos import (
    VMExecuteRequest,
    VMLogResponse,
    VMLogSaveRequest,
    VMRegisterRequest,
    VMStatusResponse,
    VMUpdateRequest,
)
from lumen_agent.application.service.common.vm_connection_service import (
    VMConnectionStatus,
    VmConnectionService,
    get_vm_connection_service,
)
from lumen_agent.config import Settings, get_settings, resolve_db_path
from lumen_agent.infrastructure.approval_registry import get_approval_registry
from lumen_agent.infrastructure.data_base.sqlite_vm_config import (
    SqliteVMConfigRepository,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/vm",
    tags=["vm"],
)

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


# ── 危险命令匹配 ──────────────────────────────────────────────────

def _load_dangerous_patterns(settings: Settings) -> list[re.Pattern]:
    """从配置加载危险命令正则模式列表。"""
    raw = settings.get("VM_DANGEROUS_COMMANDS", "rm -rf,shutdown,reboot,poweroff,init 0,init 6,dd if=,mkfs,fdisk,> /dev/sd,chmod 777 /")
    patterns = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            patterns.append(re.compile(re.escape(part), re.IGNORECASE))
    return patterns


def _is_dangerous(command: str, patterns: list[re.Pattern]) -> bool:
    """检查命令是否匹配危险模式。"""
    for p in patterns:
        if p.search(command):
            return True
    return False


# ── 辅助函数 ──────────────────────────────────────────────────────

def _get_repo(settings: Settings) -> SqliteVMConfigRepository:
    """获取 VM 配置仓储（短连接，每次请求创建）。"""
    return SqliteVMConfigRepository(resolve_db_path(settings))


def _sse_json(data: dict[str, Any]) -> str:
    """将 dict 序列化为 SSE ``data:`` 行。"""
    import json
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ══════════════════════════════════════════════════════════════════
# 注册 / 更新 / 删除
# ══════════════════════════════════════════════════════════════════


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_vm(
    body: VMRegisterRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """注册 VM 配置到数据库。若 vm_id 已存在则覆盖。"""
    repo = _get_repo(settings)
    existing = await repo.get(body.vm_id)
    result = await repo.create(body.model_dump())
    action = "覆盖" if existing else "新增"
    logger.info("VM 配置%s: vm_id=%s host=%s", action, body.vm_id, body.host)
    return {"status": "ok", "action": action, "vm": result}


@router.put("/{vm_id}")
async def update_vm(
    vm_id: str = Path(..., min_length=1),
    body: VMUpdateRequest = ...,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """更新 VM 配置（仅传入的字段被更新）。"""
    repo = _get_repo(settings)
    existing = await repo.get(vm_id)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"VM '{vm_id}' 不存在")
    # 只传入非 None 的字段
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        return {"status": "ok", "message": "无变更", "vm": existing}
    result = await repo.update(vm_id, update_data)
    logger.info("VM 配置已更新: vm_id=%s fields=%s", vm_id, list(update_data.keys()))
    return {"status": "ok", "vm": result}


@router.delete("/{vm_id}")
async def delete_vm(
    vm_id: str = Path(..., min_length=1),
    settings: Settings = Depends(get_settings),
    svc: VmConnectionService = Depends(get_vm_connection_service),
) -> dict[str, str]:
    """从 DB 删除 VM 配置（需先断开连接）。"""
    # 先断开（如果已连接）
    if svc.is_connected(vm_id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"VM '{vm_id}' 当前已连接，请先断开后再删除",
        )
    repo = _get_repo(settings)
    deleted = await repo.delete(vm_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"VM '{vm_id}' 不存在")
    logger.info("VM 配置已删除: vm_id=%s", vm_id)
    return {"status": "deleted", "vm_id": vm_id}


# ══════════════════════════════════════════════════════════════════
# 列表 / 状态 / 日志
# ══════════════════════════════════════════════════════════════════


@router.get("/list")
async def list_vms(
    settings: Settings = Depends(get_settings),
    svc: VmConnectionService = Depends(get_vm_connection_service),
) -> list[VMStatusResponse]:
    """列出所有 VM（DB 配置 + 连接状态合并）。"""
    repo = _get_repo(settings)
    rows = await repo.list_all()
    result: list[VMStatusResponse] = []
    for row in rows:
        conn = svc.get_connection(row["vm_id"])
        result.append(VMStatusResponse(
            vm_id=row["vm_id"],
            host=row["host"],
            port=row["port"],
            username=row["username"],
            description=row.get("description", ""),
            status=conn.status.value if conn else VMConnectionStatus.DISCONNECTED.value,
            last_connected_at=conn.last_connected_at if conn else None,
            error_message=conn.error_message if conn else None,
        ))
    return result


@router.get("/{vm_id}/status")
async def get_vm_status(
    vm_id: str = Path(..., min_length=1),
    settings: Settings = Depends(get_settings),
    svc: VmConnectionService = Depends(get_vm_connection_service),
) -> VMStatusResponse:
    """获取单个 VM 的配置 + 连接状态。"""
    repo = _get_repo(settings)
    row = await repo.get(vm_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"VM '{vm_id}' 不存在")
    conn = svc.get_connection(vm_id)
    return VMStatusResponse(
        vm_id=row["vm_id"],
        host=row["host"],
        port=row["port"],
        username=row["username"],
        description=row.get("description", ""),
        status=conn.status.value if conn else VMConnectionStatus.DISCONNECTED.value,
        last_connected_at=conn.last_connected_at if conn else None,
        error_message=conn.error_message if conn else None,
    )


@router.get("/{vm_id}/log")
async def get_vm_log(
    vm_id: str = Path(..., min_length=1),
    lines: int | None = None,
    settings: Settings = Depends(get_settings),
    svc: VmConnectionService = Depends(get_vm_connection_service),
) -> VMLogResponse:
    """查看 VM 的终端日志内容（已连接时读实时日志，断开后读归档日志）。"""
    # 先从连接池获取 host
    conn = svc.get_connection(vm_id)
    host = conn.config.get("host") if conn and conn.config else None

    if not host:
        # 从 DB 查
        repo = _get_repo(settings)
        row = await repo.get(vm_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"VM '{vm_id}' 不存在")
        host = row["host"]

    log_lines = svc.get_log_content(vm_id, lines=lines)
    if log_lines is None:
        # 通过 host 直接查归档
        log_lines = svc.get_log_content_for_host(host, lines=lines)
    if log_lines is None:
        return VMLogResponse(
            vm_id=vm_id,
            host=host,
            connected=svc.is_connected(vm_id),
            total_lines=0,
            lines=[],
        )

    return VMLogResponse(
        vm_id=vm_id,
        host=host,
        connected=svc.is_connected(vm_id),
        total_lines=len(log_lines),
        lines=log_lines,
    )


# ══════════════════════════════════════════════════════════════════
# 日志保存
# ══════════════════════════════════════════════════════════════════


@router.post("/{vm_id}/log/save")
async def save_vm_log(
    vm_id: str = Path(..., min_length=1),
    body: VMLogSaveRequest = ...,
    settings: Settings = Depends(get_settings),
    svc: VmConnectionService = Depends(get_vm_connection_service),
) -> dict[str, str]:
    """保存命令执行日志。由前端在 SSE 流结束后调用。"""
    success = svc.save_log(vm_id, body.command, body.output, body.exit_code)

    if not success:
        # 连接池中查不到 host 时从 DB 补充
        from lumen_agent.application.uitls.dir_guide import DirGuide
        repo = _get_repo(settings)
        row = await repo.get(vm_id)
        if row is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"VM '{vm_id}' 不存在",
            )
        host = row["host"]
        log_dir = DirGuide.machine_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{host}.log"
        if not log_file.exists():
            log_file.touch()
        success = svc.save_log(vm_id, body.command, body.output, body.exit_code)

    return {"status": "ok" if success else "error", "vm_id": vm_id}


# ══════════════════════════════════════════════════════════════════
# 连接 / 断开
# ══════════════════════════════════════════════════════════════════


@router.post("/{vm_id}/connect")
async def connect_vm(
    vm_id: str = Path(..., min_length=1),
    settings: Settings = Depends(get_settings),
    svc: VmConnectionService = Depends(get_vm_connection_service),
) -> VMStatusResponse:
    """建立 SSH 连接。若已连接则直接返回。"""
    repo = _get_repo(settings)
    config = await repo.get(vm_id)
    if config is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"VM '{vm_id}' 不存在")

    conn = await svc.connect(vm_id, config)
    if conn.status == VMConnectionStatus.ERROR:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"连接失败: {conn.error_message}",
        )

    return VMStatusResponse(
        vm_id=vm_id,
        host=config["host"],
        port=config["port"],
        username=config["username"],
        description=config.get("description", ""),
        status=conn.status.value,
        last_connected_at=conn.last_connected_at,
        error_message=conn.error_message,
    )


@router.post("/{vm_id}/disconnect")
async def disconnect_vm(
    vm_id: str = Path(..., min_length=1),
    svc: VmConnectionService = Depends(get_vm_connection_service),
) -> dict[str, str]:
    """断开 SSH 连接，日志文件自动归档为 host.YYYY-MM-DD.log。"""
    if not svc.is_connected(vm_id):
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"VM '{vm_id}' 当前未连接")
    await svc.disconnect(vm_id)
    return {"status": "disconnected", "vm_id": vm_id}


# ══════════════════════════════════════════════════════════════════
# 命令执行（SSE 流式）
# ══════════════════════════════════════════════════════════════════


@router.post("/{vm_id}/execute")
async def execute_vm_command(
    vm_id: str = Path(..., min_length=1),
    body: VMExecuteRequest = ...,
    settings: Settings = Depends(get_settings),
    svc: VmConnectionService = Depends(get_vm_connection_service),
) -> StreamingResponse:
    """SSE 流式执行命令。

    如果命令匹配危险模式，会先触发审批流程，前端弹窗确认后再执行。
    """
    # 1. 获取 VM 配置并确保连接
    repo = _get_repo(settings)
    config = await repo.get(vm_id)
    if config is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"VM '{vm_id}' 不存在")

    if not svc.is_connected(vm_id):
        conn = await svc.connect(vm_id, config)
        if conn.status == VMConnectionStatus.ERROR:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail=f"连接失败: {conn.error_message}",
            )

    command = body.command
    timeout = body.timeout
    session_id = body.session_id or f"vm-{uuid.uuid4()}"

    # 2. 检查危险命令
    dangerous_patterns = _load_dangerous_patterns(settings)
    is_dangerous = _is_dangerous(command, dangerous_patterns)

    approval_mode = settings.get("VM_APPROVAL_MODE", "dangerous")

    async def event_stream() -> AsyncIterator[str]:
        """SSE 事件流生成器。"""
        try:
            # ── 审批阶段 ─────────────────────────────────────
            if is_dangerous and approval_mode != "none":
                tool_call_id = f"vm-exec-{uuid.uuid4()}"
                approval_registry = get_approval_registry()
                await approval_registry.register(
                    session_id,
                    [{"id": tool_call_id, "name": "vm_execute", "input": {"command": command}}],
                )
                logger.info(
                    "VM 危险命令需审批: vm_id=%s command=%.80s tool_call_id=%s",
                    vm_id, command, tool_call_id,
                )

                # 向前端发出审批事件
                yield _sse_json({
                    "type": "approval",
                    "tool_call_id": tool_call_id,
                    "command": command,
                    "session_id": session_id,
                })

                # 等待审批决策
                approval_timeout = settings.get("TOOL_APPROVAL_TIMEOUT", 300)
                decisions = await approval_registry.wait_for_all(
                    session_id, timeout=approval_timeout,
                )

                if not decisions.get(tool_call_id, False):
                    yield _sse_json({"type": "done", "message": "命令已被拒绝执行"})
                    return

                logger.info("VM 危险命令已获批准: vm_id=%s command=%.80s", vm_id, command)

            # ── 执行阶段 ─────────────────────────────────────
            async for kind, data in svc.execute_stream(vm_id, command, timeout):
                if kind == "output":
                    yield _sse_json({"type": "stdout", "content": data})
                elif kind == "exit_code":
                    yield _sse_json({"type": "exit_code", "code": data})
                elif kind == "done":
                    yield _sse_json({"type": "done", "message": "命令执行完毕"})
                    return
                elif kind == "error":
                    yield _sse_json({"type": "error", "message": data})
                    return

        except asyncio.CancelledError:
            # 客户端断开 SSE 连接
            yield _sse_json({"type": "done", "message": "连接已中断"})
        except Exception as exc:
            logger.exception("VM 命令执行异常: vm_id=%s", vm_id)
            yield _sse_json({"type": "error", "message": str(exc)})
        finally:
            await get_approval_registry().unregister(session_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
