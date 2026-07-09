"""VM 连接池服务：管理 SshClient 生命周期，提供异步桥接。

核心职责：
- 连接池管理（连接/断开/状态查询）
- 同步 SSH 操作 → async 环境桥接（``run_in_executor``）
- 流式执行输出转发（``execute_stream`` → async generator）
- 日志文件生命周期管理（归档 / 查询）
"""

from __future__ import annotations

import asyncio
import logging
import queue
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from lumen_agent.application.uitls.dir_guide import DirGuide
from lumen_agent.infrastructure.virtual_machine.virtual_machine_registry import (
    SshClient,
)
from lumen_agent.infrastructure.vm_event_bus import get_vm_event_bus

logger = logging.getLogger(__name__)

_LOG_DIR = DirGuide.machine_log_dir()


class VMConnectionStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class VMConnection:
    """单个 VM 的连接状态与客户端引用。"""

    vm_id: str
    config: dict[str, Any]
    client: SshClient | None = None
    status: VMConnectionStatus = VMConnectionStatus.DISCONNECTED
    last_connected_at: str | None = None
    error_message: str | None = None


class VmConnectionService:
    """虚拟机连接池管理服务（进程级单例）。

    所有 SSH 同步操作通过 ``ThreadPoolExecutor`` 桥接到 async 上下文，
    不阻塞主事件循环。
    """

    def __init__(self, max_workers: int = 4) -> None:
        self._connections: dict[str, VMConnection] = {}
        self._thread_pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="vm-ssh",
        )

    # ── 连接管理 ─────────────────────────────────────────────────

    async def connect(self, vm_id: str, config: dict[str, Any]) -> VMConnection:
        """读 DB → 创建 SshClient → 连接 → 注册到连接池。幂等。"""
        # 已连接直接返回
        existing = self._connections.get(vm_id)
        if existing and existing.status == VMConnectionStatus.CONNECTED and existing.client and existing.client.is_connected:
            return existing

        conn = VMConnection(
            vm_id=vm_id,
            config=config,
            status=VMConnectionStatus.CONNECTING,
        )
        self._connections[vm_id] = conn

        try:
            client = SshClient(
                host=config["host"],
                port=int(config.get("port", 22)),
                username=config["username"],
                password=config["password"],
            )
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self._thread_pool, client.connect)

            conn.client = client
            conn.status = VMConnectionStatus.CONNECTED
            conn.last_connected_at = datetime.now(timezone.utc).isoformat()
            conn.error_message = None
            logger.info("VM 连接成功: vm_id=%s host=%s", vm_id, config["host"])
        except Exception as exc:
            conn.status = VMConnectionStatus.ERROR
            conn.error_message = str(exc)
            logger.error("VM 连接失败: vm_id=%s host=%s error=%s", vm_id, config["host"], exc)

        return conn

    async def disconnect(self, vm_id: str) -> None:
        """断开 SSH → 从连接池移除（日志归档在下次连接时自动完成）。"""
        conn = self._connections.pop(vm_id, None)
        if conn is None or conn.client is None:
            return

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self._thread_pool, conn.client.close)
        except Exception as exc:
            logger.warning("VM 断开清理异常: vm_id=%s error=%s", vm_id, exc)

        logger.info("VM 已断开: vm_id=%s host=%s", vm_id, conn.config.get("host"))

    async def disconnect_all(self) -> None:
        """遍历断开全部连接（供 lifespan shutdown 调用）。"""
        for vm_id in list(self._connections.keys()):
            await self.disconnect(vm_id)
        self._thread_pool.shutdown(wait=False)
        logger.info("全部 VM 连接已断开")

    # ── 非流式执行 ───────────────────────────────────────────────

    async def execute(
        self, vm_id: str, command: str, timeout: int = 30
    ) -> tuple[str, int]:
        """执行命令并完整返回输出 + 退出码。通过线程池桥接。"""
        client = self._get_connected_client(vm_id)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._thread_pool,
            client.execute,
            command,
            timeout,
        )

    # ── 流式执行 ─────────────────────────────────────────────────

    async def execute_stream(
        self, vm_id: str, command: str, timeout: int = 30
    ) -> AsyncStreamGenerator:
        """流式执行命令，返回 async generator yield ``(kind, data)``。

        kind:
          - "output"     → 命令输出增量（str）
          - "exit_code"  → 退出码（int）
          - "done"       → 执行完毕（str）
          - "error"      → 错误信息（str）
        """
        client = self._get_connected_client(vm_id)
        sync_queue: queue.Queue = queue.Queue()
        loop = asyncio.get_event_loop()

        # 先发出 command_start 事件（含命令与主机信息，供前端渲染提示符）
        cmd_start_event = {
            "type": "vm_event",
            "subtype": "command_start",
            "vm_id": vm_id,
            "data": {
                "command": command,
                "username": client.username,
                "host": client.host,
            },
            "source": "system",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await get_vm_event_bus().publish(vm_id, cmd_start_event)
        except Exception:
            pass
        yield ("command_start", cmd_start_event["data"])

        # 在线程池中启动流式执行
        future = loop.run_in_executor(
            self._thread_pool,
            client.execute_streaming,
            command,
            timeout,
            sync_queue,
        )

        try:
            while True:
                kind, data = await loop.run_in_executor(None, sync_queue.get)
                # 广播到事件总线（供 WebSocket 消费）
                if kind in ("output", "exit_code", "done", "error"):
                    try:
                        await get_vm_event_bus().publish(vm_id, {
                            "type": "vm_event",
                            "subtype": kind,
                            "vm_id": vm_id,
                            "data": data,
                            "source": "system",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                    except Exception:
                        pass  # 事件总线异常不影响命令执行

                yield (kind, data)
                if kind in ("done", "error"):
                    break
        except Exception as exc:
            logger.exception("流式读取异常")
            yield ("error", str(exc))
        finally:
            # 确保后台线程完成（不等待，仅取消）
            if not future.done():
                future.cancel()

    # ── 日志查询 ─────────────────────────────────────────────────

    def get_log_content(self, vm_id: str, *, lines: int | None = None) -> list[str] | None:
        """获取 VM 的日志内容。

        查找顺序：
        1. 当前活跃日志 ``{host}.log``（已连接）
        2. 最近归档日志 ``{host}.YYYY-MM-DD.log``

        Returns:
            日志行列表，None 表示没有可用日志。
        """
        conn = self._connections.get(vm_id)
        host = None
        if conn and conn.config:
            host = conn.config.get("host")
        if not host:
            # 尝试从已归档日志推断 host（通过 vm_id 无法直接得到 host）
            return None

        log_file = _LOG_DIR / f"{host}.log"
        if not log_file.exists():
            # 找最近的归档日志
            archived = self._find_archived_logs(host)
            if not archived:
                return None
            log_file = archived[-1]  # 最新的一个

        try:
            all_text = log_file.read_text(encoding="utf-8", errors="replace")
            all_lines = all_text.splitlines()
            if lines is not None and lines > 0:
                return all_lines[-lines:]
            return all_lines
        except OSError:
            return None

    def get_log_content_for_host(self, host: str, *, lines: int | None = None) -> list[str] | None:
        """按主机名获取日志内容（不依赖连接状态）。"""
        log_file = _LOG_DIR / f"{host}.log"
        if not log_file.exists():
            archived = self._find_archived_logs(host)
            if not archived:
                return None
            log_file = archived[-1]

        try:
            all_text = log_file.read_text(encoding="utf-8", errors="replace")
            all_lines = all_text.splitlines()
            if lines is not None and lines > 0:
                return all_lines[-lines:]
            return all_lines
        except OSError:
            return None

    def get_log_path(self, vm_id: str) -> Path | None:
        """返回 VM 的日志文件绝对路径（便于前端直接读取）。"""
        conn = self._connections.get(vm_id)
        host = conn.config.get("host") if conn and conn.config else None
        if not host:
            return None

        log_file = _LOG_DIR / f"{host}.log"
        if log_file.exists():
            return log_file

        archived = self._find_archived_logs(host)
        return archived[-1] if archived else None

    def _find_archived_logs(self, host: str) -> list[Path]:
        """查找 host 的所有归档日志 ``{host}.MM-DD_HH-MM-SS.log``。"""
        if not _LOG_DIR.exists():
            return []
        pattern = re.compile(r"^" + re.escape(host) + r"\.\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.log$")
        files = sorted(
            (f for f in _LOG_DIR.iterdir() if f.is_file() and pattern.match(f.name)),
            key=lambda p: p.name,
        )
        return files

    def save_log(
        self, vm_id: str, command: str, output: str, exit_code: int
    ) -> bool:
        """保存命令执行日志到 ``{host}.log``。

        由前端在 SSE 流式执行完成后调用。
        Returns:
            True 表示写入成功，False 表示无法解析 host 或文件不存在。
        """
        conn = self._connections.get(vm_id)
        host = conn.config.get("host") if conn and conn.config else None
        if not host:
            return False

        log_file = _LOG_DIR / f"{host}.log"
        if not log_file.exists():
            return False

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(command)
                if not command.endswith("\n"):
                    f.write("\n")
                if output:
                    f.write(output)
                    if not output.endswith("\n"):
                        f.write("\n")
            return True
        except OSError as exc:
            logger.warning("日志保存失败: host=%s error=%s", host, exc)
            return False

    # ── 状态查询 ─────────────────────────────────────────────────

    def get_connection(self, vm_id: str) -> VMConnection | None:
        return self._connections.get(vm_id)

    def get_status(self, vm_id: str) -> VMConnectionStatus:
        conn = self._connections.get(vm_id)
        if conn is None:
            return VMConnectionStatus.DISCONNECTED
        return conn.status

    def list_connections(self) -> list[VMConnection]:
        return list(self._connections.values())

    def is_connected(self, vm_id: str) -> bool:
        conn = self._connections.get(vm_id)
        return conn is not None and conn.status == VMConnectionStatus.CONNECTED and conn.client is not None

    # ── 内部 ─────────────────────────────────────────────────────

    def _get_connected_client(self, vm_id: str) -> SshClient:
        conn = self._connections.get(vm_id)
        if conn is None or conn.client is None or not conn.client.is_connected:
            raise ConnectionError(f"VM '{vm_id}' 未连接，请先调用 connect()")
        return conn.client


# ── 类型别名 ─────────────────────────────────────────────────────

AsyncStreamGenerator = Any  # typing: AsyncIterator[tuple[str, Any]]

#-------------------------

def get_machine_log_dir()-> Path:
    return _LOG_DIR


# ── 全局单例 ─────────────────────────────────────────────────────

_service: VmConnectionService | None = None


def get_vm_connection_service() -> VmConnectionService:
    """返回全局唯一的 VmConnectionService 实例。"""
    global _service
    if _service is None:
        _service = VmConnectionService()
    return _service
