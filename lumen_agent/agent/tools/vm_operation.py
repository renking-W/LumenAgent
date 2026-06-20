"""VirtualMachineOperation 工具：让 LLM Agent 操作已注册的虚拟机。

支持的操作：
- exec_command：在虚拟机上执行 shell 命令
- connect：连接虚拟机
- disconnect：断开虚拟机
- get_status：查询虚拟机状态
- list_vms：列出所有已注册的虚拟机及其状态
"""

from __future__ import annotations

import logging

from lumen_agent.agent.tools.base import BaseTool, ToolResult
from lumen_agent.agent.tools.registry import ToolRegistry
from lumen_agent.application.service.vm_connection_service import (
    get_vm_connection_service,
)
from lumen_agent.config import get_settings, resolve_db_path
from lumen_agent.infrastructure.data_base.sqlite_vm_config import (
    SqliteVMConfigRepository,
)

logger = logging.getLogger(__name__)


def _get_vm_repo() -> SqliteVMConfigRepository:
    """获取 VM 配置仓储（短连接）。"""
    settings = get_settings()
    return SqliteVMConfigRepository(resolve_db_path(settings))


@ToolRegistry.register
class VirtualMachineOperation(BaseTool):
    """在已注册的虚拟机上执行操作：执行命令、连接、断开、查看状态。"""

    name = "virtual_machine_operation"
    description = (
        "对已注册的虚拟机执行操作。"
        "支持的操作：exec_command(执行shell命令), connect(连接), "
        "disconnect(断开), get_status(查看状态), list_vms(列出所有虚拟机)。"
        "执行命令前会自动建立连接。"
    )
    requires_approval = True
    parameters = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["exec_command", "connect", "disconnect", "get_status", "list_vms"],
                "description": "要执行的操作类型。exec_command=执行命令, connect=建立连接, disconnect=断开连接, get_status=查看状态, list_vms=列出所有VM",
            },
            "vm_id": {
                "type": "string",
                "description": "虚拟机 ID（list_vms 操作时可选，其余操作必填）",
            },
            "command": {
                "type": "string",
                "description": "当 operation 为 exec_command 时要执行的 shell 命令",
            },
            "timeout": {
                "type": "integer",
                "description": "命令执行超时秒数，默认 30",
                "default": 30,
            },
        },
        "required": ["operation"],
    }

    async def execute(self, params: dict) -> ToolResult:
        operation = params.get("operation", "")
        vm_id = params.get("vm_id", "")
        svc = get_vm_connection_service()

        if operation == "exec_command":
            return await self._exec_command(svc, vm_id, params)
        elif operation == "connect":
            return await self._connect(svc, vm_id)
        elif operation == "disconnect":
            return await self._disconnect(svc, vm_id)
        elif operation == "get_status":
            return await self._get_status(svc, vm_id)
        elif operation == "list_vms":
            return await self._list_vms(svc)
        else:
            return ToolResult.error(
                f"不支持的操作: '{operation}'。"
                f"可选: exec_command, connect, disconnect, get_status, list_vms"
            )

    async def _exec_command(
        self, svc, vm_id: str, params: dict
    ) -> ToolResult:
        """执行命令：自动连接 → 流式执行 → 返回完整输出。"""
        if not vm_id:
            return ToolResult.error("exec_command 需要指定 vm_id")
        command = params.get("command", "").strip()
        if not command:
            return ToolResult.error("exec_command 需要指定 command")
        timeout = params.get("timeout", 30)

        # 确保 VM 已连接
        if not svc.is_connected(vm_id):
            repo = _get_vm_repo()
            config = await repo.get(vm_id)
            if config is None:
                return ToolResult.error(f"VM '{vm_id}' 不存在，请先注册或使用 list_vms 查看可用 VM")
            conn = await svc.connect(vm_id, config)
            from lumen_agent.application.service.vm_connection_service import (
                VMConnectionStatus,
            )
            if conn.status == VMConnectionStatus.ERROR:
                return ToolResult.error(f"VM '{vm_id}' 连接失败: {conn.error_message}")
            logger.info("VM '%s' 已自动连接（执行命令前）", vm_id)

        # 流式执行并积累输出
        full_output = ""
        exit_code = None
        try:
            async for kind, data in svc.execute_stream(vm_id, command, timeout):
                if kind == "output":
                    full_output += data
                elif kind == "exit_code":
                    exit_code = data
                    full_output += f"\n[退出码: {data}]"
                elif kind == "error":
                    return ToolResult.error(str(data))
                # kind == "done" → 正常结束，继续
        except ConnectionError as e:
            return ToolResult.error(f"VM 连接异常: {e}")
        except Exception as e:
            logger.exception("VM 命令执行异常: vm_id=%s", vm_id)
            return ToolResult.error(f"执行异常: {e}")

        result = full_output.strip() or "(无输出)"
        logger.info(
            "VM 命令执行完成: vm_id=%s exit_code=%s output_len=%d",
            vm_id, exit_code, len(result),
        )
        return ToolResult.success(result)

    async def _connect(self, svc, vm_id: str) -> ToolResult:
        """连接虚拟机。"""
        if not vm_id:
            return ToolResult.error("connect 需要指定 vm_id")
        if svc.is_connected(vm_id):
            return ToolResult.success(f"VM '{vm_id}' 已处于连接状态")

        repo = _get_vm_repo()
        config = await repo.get(vm_id)
        if config is None:
            return ToolResult.error(f"VM '{vm_id}' 不存在，请先注册或使用 list_vms 查看可用 VM")

        from lumen_agent.application.service.vm_connection_service import (
            VMConnectionStatus,
        )
        conn = await svc.connect(vm_id, config)
        if conn.status == VMConnectionStatus.ERROR:
            return ToolResult.error(f"连接失败: {conn.error_message}")

        return ToolResult.success(
            f"VM '{vm_id}' ({config.get('host')}:{config.get('port')}) 连接成功"
        )

    async def _disconnect(self, svc, vm_id: str) -> ToolResult:
        """断开虚拟机连接。"""
        if not vm_id:
            return ToolResult.error("disconnect 需要指定 vm_id")
        if not svc.is_connected(vm_id):
            return ToolResult.success(f"VM '{vm_id}' 当前未连接，无需断开")
        await svc.disconnect(vm_id)
        return ToolResult.success(f"VM '{vm_id}' 已断开连接")

    async def _get_status(self, svc, vm_id: str) -> ToolResult:
        """查看虚拟机状态。"""
        if not vm_id:
            return ToolResult.error("get_status 需要指定 vm_id")

        # 先查 DB 配置
        repo = _get_vm_repo()
        config = await repo.get(vm_id)
        if config is None:
            return ToolResult.error(f"VM '{vm_id}' 不存在")

        # 再查连接状态
        status = svc.get_status(vm_id)
        conn = svc.get_connection(vm_id)

        return ToolResult.success({
            "vm_id": vm_id,
            "host": config.get("host"),
            "port": config.get("port"),
            "username": config.get("username"),
            "description": config.get("description", ""),
            "status": status.value if hasattr(status, "value") else str(status),
            "last_connected_at": conn.last_connected_at if conn else None,
            "error_message": conn.error_message if conn else None,
        })

    async def _list_vms(self, svc) -> ToolResult:
        """列出所有已注册的虚拟机及其状态。"""
        repo = _get_vm_repo()
        rows = await repo.list_all()
        if not rows:
            return ToolResult.success("当前没有已注册的虚拟机。你可以通过 API 注册一台 VM 后再操作。")

        result = []
        for row in rows:
            vm_id = row["vm_id"]
            status = svc.get_status(vm_id)
            conn = svc.get_connection(vm_id)
            result.append({
                "vm_id": vm_id,
                "host": row.get("host"),
                "port": row.get("port"),
                "username": row.get("username"),
                "description": row.get("description", ""),
                "status": status.value if hasattr(status, "value") else str(status),
                "last_connected_at": conn.last_connected_at if conn else None,
            })

        return ToolResult.success({
            "total": len(result),
            "vms": result,
        })
