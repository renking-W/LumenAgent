"""Bash 工具：在子进程中执行 shell 命令并返回输出。"""

from __future__ import annotations

import asyncio
import platform
import sys

from lumen_agent.agent.tools.base import BaseTool, ToolResult
from lumen_agent.agent.tools.registry import ToolRegistry

_DEFAULT_TIMEOUT = 30          # 秒
_MAX_TIMEOUT = 120             # 秒，防止工具循环阻塞太久
_MAX_OUTPUT_BYTES = 50 * 1024  # 50 KB，与 read 对齐
_OUTPUT_HINT = "输出超过 50KB，已截断；若需完整结果请将输出重定向到文件再用 read 读取。"

# Windows 下默认用 PowerShell；Unix 下用 /bin/bash
_IS_WINDOWS = platform.system() == "Windows"


@ToolRegistry.register
class Bash(BaseTool):
    """在系统 shell 中执行命令，返回 stdout/stderr 及退出码。"""

    name = "bash"
    description = (
        "在系统 shell 中执行命令并返回输出（stdout + stderr 合并）。"
        + ("目前是 Windows 系统下请使用 PowerShell；" if _IS_WINDOWS else "目前是 Unix 系统下请使用 /bin/bash；")
        + "单次输出上限 50KB；超出自动截断并提示。"
        "默认超时 30 秒，可通过 timeout 参数设置（最大 120 秒）。"
        "不要用此工具运行需要交互式输入的命令。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的 shell 命令字符串。",
            },
            "working_directory": {
                "type": "string",
                "description": (
                    "命令的工作目录（绝对路径或相对 workspace 的路径）。"
                    "可选，默认为 workspace 目录。"
                ),
            },
            "timeout": {
                "type": "integer",
                "description": f"超时秒数，默认 {_DEFAULT_TIMEOUT}，最大 {_MAX_TIMEOUT}。可选。",
            },
        },
        "required": ["command"],
    }

    async def execute(self, params: dict) -> ToolResult:
        command: str = str(params.get("command", "")).strip()
        if not command:
            return ToolResult.error("command 不能为空。")

        # 解析工作目录
        cwd_raw: str | None = params.get("working_directory")
        if cwd_raw:
            cwd = _resolve_cwd(cwd_raw.strip())
            if cwd is None:
                return ToolResult.error(f"working_directory 路径无效或不存在：'{cwd_raw}'。")
        else:
            from lumen_agent.config import get_settings
            cwd = get_settings().workspace_dir_resolved()

        # 超时
        timeout_val = params.get("timeout")
        try:
            timeout = int(timeout_val) if timeout_val is not None else _DEFAULT_TIMEOUT
        except (TypeError, ValueError):
            return ToolResult.error("timeout 须为整数（秒）。")
        if timeout < 1 or timeout > _MAX_TIMEOUT:
            return ToolResult.error(f"timeout 须在 1～{_MAX_TIMEOUT} 秒之间。")

        # 构造子进程参数
        if _IS_WINDOWS:
            proc_args: list[str] = ["powershell", "-NoProfile", "-Command", command]
        else:
            proc_args = ["/bin/bash", "-c", command]

        try:
            proc = await asyncio.create_subprocess_exec(
                *proc_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,  # 合并 stderr → stdout
                cwd=str(cwd),
            )
            try:
                stdout_bytes, _ = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return ToolResult.error(
                    f"命令执行超时（{timeout} 秒），进程已终止。"
                )
        except FileNotFoundError as exc:
            return ToolResult.error(f"Shell 不可用：{exc}")
        except OSError as exc:
            return ToolResult.error(f"无法启动子进程：{exc}")

        exit_code: int = proc.returncode or 0

        # 截断输出
        truncated = False
        if len(stdout_bytes) > _MAX_OUTPUT_BYTES:
            stdout_bytes = stdout_bytes[:_MAX_OUTPUT_BYTES]
            truncated = True

        output = stdout_bytes.decode(
            sys.stdout.encoding or "utf-8", errors="replace"
        )

        header = f"[exit_code: {exit_code}]\n"
        footer = f"\n[{_OUTPUT_HINT}]" if truncated else ""
        full = header + output + footer

        if exit_code != 0:
            return ToolResult.error(full)
        return ToolResult.success(full)


def _resolve_cwd(raw: str) -> object:
    """解析工作目录；不存在或不是目录时返回 None。"""
    from pathlib import Path
    try:
        p = Path(raw).expanduser()
        if not p.is_absolute():
            from lumen_agent.config import get_settings
            p = get_settings().workspace_dir_resolved() / p
        p = p.resolve()
    except (OSError, RuntimeError):
        return None
    return p if p.is_dir() else None
