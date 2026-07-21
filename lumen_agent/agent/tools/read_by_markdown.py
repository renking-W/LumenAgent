"""ReadByMarkdown 工具：将特殊本地文档转换为 Markdown 后读取。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from lumen_agent.agent.tools.base import BaseTool, ToolResult
from lumen_agent.agent.tools.read import _resolve_path
from lumen_agent.agent.tools.registry import ToolRegistry
from lumen_agent.application.uitls.document_reader import (
    DocumentReadError,
    read_by_markitdown,
)

_MAX_LINES = 2000
_MAX_BYTES = 50 * 1024
_LIMIT_HINT = "单次最多 2000 行且不超过 50KB，请使用 offset/limit 分块读取。"


@ToolRegistry.register
class ReadByMarkdown(BaseTool):
    """通过 MarkItDown 读取 CSV、Office 文档和 PDF。"""

    name = "read_by_markdown"
    description = (
        "将本地 CSV、DOCX、XLSX、DOC、PPTX、PPT、PDF 文件转换为 Markdown 后读取。"
        "仅支持这些扩展名；其他文件必须使用 read。"
        "相对路径相对于 workspace，绝对路径与 ~ 可直接使用。"
        "单次返回最多 2000 行、50KB，超出请用 offset/limit 分块读取。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "要读取的本地文件路径。",
            },
            "offset": {
                "type": "integer",
                "description": "转换后 Markdown 的起始行号，从 0 开始。可选。",
            },
            "limit": {
                "type": "integer",
                "description": f"最多返回的行数，不得超过 {_MAX_LINES}。可选。",
            },
        },
        "required": ["path"],
    }

    async def execute(self, params: dict) -> ToolResult:
        raw_path = str(params.get("path", "")).strip()
        if not raw_path:
            return ToolResult.error("Path is empty.")

        try:
            full_path: Path = _resolve_path(raw_path)
            text = await asyncio.to_thread(read_by_markitdown, full_path)
        except (DocumentReadError, OSError, RuntimeError) as exc:
            return ToolResult.error(f"无法读取文件 '{raw_path}'：{exc}")

        try:
            offset = max(0, int(params.get("offset") or 0))
            limit = int(params.get("limit") or _MAX_LINES)
        except (TypeError, ValueError):
            return ToolResult.error("offset 和 limit 必须是整数。")
        if limit < 1 or limit > _MAX_LINES:
            return ToolResult.error(f"limit 必须在 1 到 {_MAX_LINES} 之间。")

        lines = text.splitlines(keepends=True)
        if offset >= len(lines):
            return ToolResult.success("")
        content = "".join(lines[offset : offset + limit])
        if len(content.encode("utf-8")) > _MAX_BYTES:
            return ToolResult.error(f"读取结果超过 50KB 上限。{_LIMIT_HINT}")
        return ToolResult.success(content)
