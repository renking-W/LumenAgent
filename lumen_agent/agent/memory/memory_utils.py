"""记忆文件工具类：统一处理 memory 目录下的读写与路径逻辑。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class MemoryFileUtils:
    """记忆文件相关的统一工具类。"""

    memory_dir: Path

    @classmethod
    def from_workspace_path(cls, workspace_path: Path) -> "MemoryFileUtils":
        """根据 work_space 路径定位到项目 memory 目录。"""
        return cls(memory_dir=workspace_path / "memory")

    def ensure_dir(self) -> Path:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        return self.memory_dir

    def memory_file_path(self) -> Path:
        return self.memory_dir.parent / "MEMORY.md"

    def daily_file_path(self, target_date: date | None = None) -> Path:
        d = target_date or date.today()
        return self.memory_dir / f"{d.isoformat()}.md"

    def exists(self, path: Path) -> bool:
        return path.exists()

    def file_size(self, path: Path) -> int:
        return path.stat().st_size if path.exists() else 0

    def read_text_if_exists(self, path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _contains_entry_marker(text: str, marker: str) -> bool:
        """精确匹配条目标记，避免短区间 ID 命中长区间 ID 的前缀。"""
        return re.search(rf"{re.escape(marker)}(?:\s|$)", text) is not None

    def _find_entry_file(self, marker: str, fallback: Path) -> tuple[Path, str]:
        """在全部每日记忆中定位已有条目，支持任务跨日期重试。"""
        for path in sorted(self.memory_dir.glob("*.md")):
            content = self.read_text_if_exists(path)
            if self._contains_entry_marker(content, marker):
                return path, content
        return fallback, self.read_text_if_exists(fallback)

    def append_daily_summary(
        self,
        session_id: str,
        count_summary: str,
        *,
        entry_id: str,
    ) -> tuple[Path, str] | None:
        """按稳定条目 ID 写入当日记忆；同一区间重试时覆盖原条目。"""
        body = (count_summary or "").strip()
        if not body:
            return None

        self.ensure_dir()
        now = datetime.now().astimezone()
        file_path = self.daily_file_path(now.date())
        ts = now.strftime('%Y-%m-%d %H:%M:%S')
        marker = f"entry_id={entry_id}"
        file_path, existing = self._find_entry_file(marker, file_path)
        blocks = [block.strip() for block in existing.split("\n---\n") if block.strip()]

        # 重试同一区间时沿用原时间戳，使 Markdown 和向量内容都保持稳定。
        for block in blocks:
            if not self._contains_entry_marker(block, marker):
                continue
            match = re.match(r"^##\s+(.+?)\s+session=", block)
            if match:
                ts = match.group(1)
            break

        header = f"## {ts}  session={session_id}  {marker}\n\n"
        new_block = f"{header}{body}".strip()
        replaced = False
        for index, block in enumerate(blocks):
            if self._contains_entry_marker(block, marker):
                blocks[index] = new_block
                replaced = True
                break
        if not replaced:
            blocks.append(new_block)

        file_path.write_text(
            "\n\n---\n\n".join(blocks) + "\n\n---\n\n",
            encoding="utf-8",
        )
        return file_path, ts

    def append_message_backup(
        self,
        *,
        session_id: str,
        messages: list[dict[str, Any]],
        role_label_map: dict[str, str],
        message_to_text_fn: Callable[[dict[str, Any]], str],
        entry_id: str,
    ) -> Path:
        """按稳定条目 ID 写入强制截断原文，同一区间重试时覆盖旧条目。"""
        self.ensure_dir()
        now = datetime.now()
        file_path = self.memory_dir / f"{now.strftime('%Y-%m-%d')}.md"
        marker = f"entry_id={entry_id}"
        parts: list[str] = [
            f"## {now.strftime('%Y-%m-%d %H:%M:%S')}  "
            f"session={session_id}  {marker}  type=backup（强制截断记录）\n\n"
        ]
        for msg in messages:
            label = role_label_map.get(msg.get("role", ""), msg.get("role", ""))
            parts.append(f"**{label}**: {message_to_text_fn(msg)}\n\n")
        new_block = "".join(parts).strip()

        file_path, existing = self._find_entry_file(marker, file_path)
        blocks = [block.strip() for block in existing.split("\n---\n") if block.strip()]
        replaced = False
        for index, block in enumerate(blocks):
            if self._contains_entry_marker(block, marker):
                blocks[index] = new_block
                replaced = True
                break
        if not replaced:
            blocks.append(new_block)

        file_path.write_text(
            "\n\n---\n\n".join(blocks) + "\n\n---\n\n",
            encoding="utf-8",
        )
        return file_path
