"""VM 模块的 Pydantic 请求/响应模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ── 请求体 ─────────────────────────────────────────────────────────


class VMRegisterRequest(BaseModel):
    """注册 VM 到 DB。"""

    vm_id: str = Field(..., min_length=1, max_length=64, description="自定义名称，如 ubuntu-dev")
    host: str = Field(..., min_length=1, description="IP 或域名")
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    description: str = Field(default="")


class VMUpdateRequest(BaseModel):
    """更新 VM 配置（全部可选，仅传入的字段被更新）。"""

    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = None
    password: str | None = None
    description: str | None = None


class VMExecuteRequest(BaseModel):
    """执行命令。"""

    command: str = Field(..., min_length=1, description="要执行的 shell 命令")
    session_id: str = Field(default="", description="用于审批传递")
    timeout: int = Field(default=30, ge=1, le=300, description="超时秒数")


class VMLogSaveRequest(BaseModel):
    """前端在 SSE 流结束后，主动保存命令执行日志。"""

    command: str = Field(..., min_length=1, description="执行的命令")
    output: str = Field(default="", description="命令输出（已去除标记，纯文本）")
    exit_code: int = Field(default=0, description="退出码")


# ── 响应体 ─────────────────────────────────────────────────────────


class VMInfo(BaseModel):
    """VM 基本信息（DB 配置）。"""

    vm_id: str
    host: str
    port: int
    username: str
    description: str
    created_at: str
    updated_at: str


class VMConnectionStatus(BaseModel):
    """VM 连接状态。"""

    vm_id: str
    host: str
    status: Literal["disconnected", "connecting", "connected", "error"]
    last_connected_at: str | None = None
    error_message: str | None = None


class VMStatusResponse(BaseModel):
    """VM 配置 + 连接状态的合并响应。"""

    vm_id: str
    host: str
    port: int
    username: str
    description: str
    status: Literal["disconnected", "connecting", "connected", "error"]
    last_connected_at: str | None = None
    error_message: str | None = None


class VMLogResponse(BaseModel):
    """VM 日志响应。"""

    vm_id: str
    host: str
    connected: bool
    total_lines: int
    lines: list[str]


class VMExecuteResponse(BaseModel):
    """非流式执行响应。"""

    vm_id: str
    command: str
    exit_code: int
    output: str
    execution_time: float
