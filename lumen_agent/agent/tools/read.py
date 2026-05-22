"""Read 工具：按路径读取文件内容。"""

from __future__ import annotations

from pathlib import Path

from lumen_agent.agent.tools.base import BaseTool, ToolResult
from lumen_agent.agent.tools.registry import ToolRegistry

_MAX_LINES = 2000
_MAX_BYTES = 50 * 1024  # 50 KB
_LIMIT_HINT = "单次最多 2000 行且不超过 50KB，请使用 offset/limit 分块读取。"


def _resolve_path(raw: str) -> Path:
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p.resolve()
    from lumen_agent.config import get_settings
    return (get_settings().workspace_dir_resolved() / p).resolve()


@ToolRegistry.register
class Read(BaseTool):
    """读取本地普通文件内容。"""

    name = "read"
    description = (
        "读取普通文件内容。"
        "相对路径相对于 workspace；绝对路径与 ~ 可直接使用。"
        "单次返回最多 2000 行、50KB（UTF-8）；超出请用 offset/limit 分块读取。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "文件路径：绝对路径。必填"
                ),
            },
            "offset": {
                "type": "integer",
                "description": "起始行号，从 0 开始且包含该行。可选。",
            },
            "limit": {
                "type": "integer",
                "description": f"最多返回的行数，单次不得超过 {_MAX_LINES}。可选，默认按上限截断。",
            },
        },
        "required": ["path"],
    }

    async def execute(self, params: dict) -> ToolResult:
        raw_path: str = str(params.get("path", "")).strip()
        if not raw_path:
            return ToolResult.error("Path is empty.")

        try:
            full_path = _resolve_path(raw_path)
        except (OSError, RuntimeError) as exc:
            return ToolResult.error(f"路径无效 '{raw_path}'：{exc}")

        if not full_path.exists():
            return ToolResult.error(f"路径不存在：'{raw_path}'。")

        if full_path.is_dir():
            return ToolResult.error(f"路径为目录，read 仅支持文件：'{raw_path}'。")

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError as exc:
            return ToolResult.error(f"无法读取文件 '{raw_path}'：{exc}")

        offset: int = max(0, int(params.get("offset") or 0))
        if offset >= len(lines):
            return ToolResult.success("")

        limit_val = params.get("limit")
        if limit_val is not None:
            limit = int(limit_val)
            if limit < 1:
                return ToolResult.error("limit 须 >= 1。")
            if limit > _MAX_LINES:
                return ToolResult.error(f"limit 不能超过 {_MAX_LINES} 行。{_LIMIT_HINT}")
        else:
            limit = _MAX_LINES

        sliced = lines[offset : offset + limit]
        content = "".join(sliced)

        if len(content.encode("utf-8")) > _MAX_BYTES:
            return ToolResult.error(
                f"读取结果超过 50KB 上限。{_LIMIT_HINT}"
            )

        return ToolResult.success(content)
