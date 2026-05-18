"""Read 工具：读取工作目录内的文件或列出目录。"""

from __future__ import annotations

import os
from pathlib import Path

from lumen_agent.agent.tools.base import BaseTool, ToolResult
from lumen_agent.agent.tools.registry import ToolRegistry

_MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB


def _get_workspace_dir() -> Path:
    """延迟读取 Settings，避免循环导入；解析为绝对路径。"""
    from lumen_agent.config import get_settings
    settings = get_settings()
    workspace = Path(settings.agent_workspace_dir)
    if not workspace.is_absolute():
        from lumen_agent.config import _PACKAGE_DIR  # type: ignore[attr-defined]
        workspace = _PACKAGE_DIR / workspace
    return workspace.resolve()


@ToolRegistry.register
class Read(BaseTool):
    """读取工作目录内的文件内容或列出目录条目。"""

    name = "read"
    description = (
        "Read the contents of a file or list entries of a directory "
        "inside the workspace. "
        "Use `offset` and `limit` to read a slice of a large file."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File or directory path, relative to the workspace root.",
            },
            "offset": {
                "type": "integer",
                "description": "Starting line number (0-indexed, inclusive). Optional.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to return. Optional.",
            },
        },
        "required": ["path"],
    }

    async def execute(self, params: dict) -> ToolResult:
        raw_path: str = params.get("path", "")
        workspace = _get_workspace_dir()
        full_path = self._resolve_safe_path(raw_path, workspace)

        if full_path is None:
            return ToolResult.error(
                f"Path '{raw_path}' is outside the workspace directory."
            )

        if not full_path.exists():
            return ToolResult.error(f"Path '{raw_path}' does not exist.")

        if full_path.is_dir():
            entries = os.listdir(full_path)
            return ToolResult.success("\n".join(sorted(entries)))

        size = full_path.stat().st_size
        if size > _MAX_FILE_SIZE:
            return ToolResult.error(
                f"File '{raw_path}' is too large ({size} bytes > 1 MB limit). "
                "Use offset/limit to read a portion."
            )

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError as exc:
            return ToolResult.error(f"Cannot read '{raw_path}': {exc}")

        offset: int = max(0, int(params.get("offset") or 0))
        limit_val = params.get("limit")
        limit: int = int(limit_val) if limit_val is not None else len(lines)

        sliced = lines[offset : offset + limit]
        content = "".join(sliced)
        return ToolResult.success(content)

    @staticmethod
    def _resolve_safe_path(raw_path: str, workspace: Path) -> Path | None:
        """解析路径并校验必须在工作目录内（防目录穿越）。"""
        try:
            target = (workspace / raw_path).resolve()
            target.relative_to(workspace)
            return target
        except (ValueError, OSError):
            return None
