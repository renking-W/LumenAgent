"""Write 工具：覆盖、追加或按片段替换文件内容（UTF-8）。"""

from __future__ import annotations

from pathlib import Path

from lumen_agent.agent.tools.base import BaseTool, ToolResult
from lumen_agent.agent.tools.registry import ToolRegistry

_MAX_LINES = 2000
_MAX_BYTES = 50 * 1024  # 50 KB
_LIMIT_HINT = "单次最多 2000 行且不超过 50KB，请分块写入。"


def _resolve_path(raw: str) -> Path:
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p.resolve()
    from lumen_agent.config import get_settings, resolve_workspace_dir
    return (resolve_workspace_dir(get_settings()) / p).resolve()


def _check_payload(text: str, label: str) -> ToolResult | None:
    line_count = len(text.splitlines()) if text else 0
    byte_count = len(text.encode("utf-8"))
    if line_count > _MAX_LINES:
        return ToolResult.error(
            f"{label} 超过行数上限（{line_count} 行 > {_MAX_LINES} 行）。{_LIMIT_HINT}"
        )
    if byte_count > _MAX_BYTES:
        return ToolResult.error(
            f"{label} 超过体积上限（{byte_count} 字节 > {_MAX_BYTES} 字节，约 50KB）。{_LIMIT_HINT}"
        )
    return None


@ToolRegistry.register
class Write(BaseTool):
    """写入文件：整文件覆盖、末尾追加，或对已有文件做一次唯一子串替换。"""

    name = "write"
    description = (
        "写入文本文件（UTF-8）。支持三种方式："
        "1）默认：用 content 整文件创建或覆盖；"
        "2）append 为 true：将 content 追加到文件末尾；"
        "3）提供 old_string 与 new_string：在已存在文件中唯一替换第一段 old_string。"
        "相对路径相对于 workspace；缺父目录会自动创建。"
        "单次 content / old_string / new_string 均最多 2000 行、50KB（UTF-8），超出请分块写入。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "目标文件路径：绝对路径。必填"
                ),
            },
            "content": {
                "type": "string",
                "description": (
                    "要写入的 UTF-8 文本（单次最多 2000 行、50KB）。"
                    "整文件覆盖或追加时必填；仅做替换时不要求。"
                ),
            },
            "append": {
                "type": "boolean",
                "description": (
                    "为 true 时将 content 追加到文件末尾，不覆盖原内容。"
                    "不可与 old_string/new_string 替换同时使用。"
                ),
            },
            "old_string": {
                "type": "string",
                "description": (
                    "与 new_string 一起用于局部替换（各最多 2000 行、50KB）；"
                    "在文件正文中必须恰好出现一次。不能与 append 同时使用。"
                ),
            },
            "new_string": {
                "type": "string",
                "description": "替换 old_string 的文本（最多 2000 行、50KB）；可为空字符串。",
            },
        },
        "required": ["path"],
    }

    async def execute(self, params: dict) -> ToolResult:
        raw_path: str = str(params.get("path", "")).strip()
        if not raw_path:
            return ToolResult.error("Path is empty.")

        append_flag = bool(params.get("append"))
        old_raw = params.get("old_string")
        has_replace = old_raw is not None
        new_raw = params.get("new_string")

        if append_flag and has_replace:
            return ToolResult.error("不能同时设置 append 与 old_string/new_string 替换。")

        if has_replace:
            if not isinstance(old_raw, str):
                old_raw = str(old_raw)
            if old_raw == "":
                return ToolResult.error("替换模式下 old_string 不能为空。")
            if new_raw is None:
                return ToolResult.error("替换模式下必须提供 new_string。")
            new_str: str = new_raw if isinstance(new_raw, str) else str(new_raw)
            if err := _check_payload(old_raw, "old_string"):
                return err
            if err := _check_payload(new_str, "new_string"):
                return err
            return await self._execute_replace(raw_path, old_raw, new_str)

        if append_flag:
            if "content" not in params:
                return ToolResult.error("追加模式需要参数 content。")
            content = str(params["content"])
            if err := _check_payload(content, "写入内容"):
                return err
            return await self._execute_append(raw_path, content)

        if "content" not in params:
            return ToolResult.error("整文件写入需要参数 content；或提供 old_string/new_string 做替换。")
        content = str(params["content"])
        if err := _check_payload(content, "写入内容"):
            return err
        return await self._execute_overwrite(raw_path, content)

    async def _execute_overwrite(self, raw_path: str, content: str) -> ToolResult:
        full_path, err = self._prepare(raw_path)
        if err:
            return err
        try:
            with open(full_path, "w", encoding="utf-8", newline="") as fh:
                fh.write(content)
        except OSError as exc:
            return ToolResult.error(f"无法写入文件 '{raw_path}'：{exc}")
        return ToolResult.success(
            f"已覆盖写入 {len(content.encode('utf-8'))} 字节（UTF-8）：{full_path}"
        )

    async def _execute_append(self, raw_path: str, content: str) -> ToolResult:
        full_path, err = self._prepare(raw_path)
        if err:
            return err
        try:
            with open(full_path, "a", encoding="utf-8", newline="") as fh:
                fh.write(content)
        except OSError as exc:
            return ToolResult.error(f"无法追加写入文件 '{raw_path}'：{exc}")
        return ToolResult.success(
            f"已追加 {len(content.encode('utf-8'))} 字节（UTF-8）：{full_path}"
        )

    async def _execute_replace(
        self, raw_path: str, old_string: str, new_string: str
    ) -> ToolResult:
        full_path, err = self._prepare(raw_path)
        if err:
            return err

        if not full_path.is_file():
            return ToolResult.error(f"替换模式要求文件已存在且为普通文件：'{raw_path}'。")

        if full_path.stat().st_size > _MAX_BYTES:
            return ToolResult.error(
                f"文件过大（> {_MAX_BYTES} 字节），无法用替换模式一次性处理。{_LIMIT_HINT}"
            )

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            return ToolResult.error(f"无法读取文件 '{raw_path}'：{exc}")

        if err_msg := _check_payload(text, "待替换文件内容"):
            return ToolResult.error(err_msg)

        count = text.count(old_string)
        if count == 0:
            return ToolResult.error("未在文件中找到 old_string。")
        if count > 1:
            return ToolResult.error(
                f"old_string 在文件中出现 {count} 次，须恰好出现 1 次才能替换。"
            )

        new_text = text.replace(old_string, new_string, 1)
        try:
            with open(full_path, "w", encoding="utf-8", newline="") as fh:
                fh.write(new_text)
        except OSError as exc:
            return ToolResult.error(f"无法写回文件 '{raw_path}'：{exc}")

        return ToolResult.success(
            f"已替换一段内容并写回（UTF-8 共 {len(new_text.encode('utf-8'))} 字节）：{full_path}"
        )

    def _prepare(self, raw_path: str) -> tuple[Path, ToolResult | None]:
        try:
            full_path = _resolve_path(raw_path)
        except (OSError, RuntimeError) as exc:
            return Path(), ToolResult.error(f"路径无效 '{raw_path}'：{exc}")

        if full_path.exists() and full_path.is_dir():
            return full_path, ToolResult.error(f"路径为目录，write 仅支持文件：'{raw_path}'。")

        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return full_path, ToolResult.error(f"无法创建父目录：{exc}")

        return full_path, None
