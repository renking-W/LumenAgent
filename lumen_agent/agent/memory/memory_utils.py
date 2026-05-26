"""记忆文件工具类：统一处理 memory 目录下的读写与路径逻辑。"""

from __future__ import annotations

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
        return self.memory_dir / "MEMORY.md"

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

    def append_daily_summary(self, session_id: str, count_summary: str) -> Path | None:
        body = (count_summary or "").strip()
        if not body:
            return None

        self.ensure_dir()
        now = datetime.now().astimezone()
        file_path = self.daily_file_path(now.date())
        header = f"## {now.strftime('%Y-%m-%d %H:%M:%S')}  session={session_id}\n\n"

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(header)
            f.write(body)
            f.write("\n\n---\n\n")
        return file_path

    def append_message_backup(
        self,
        *,
        session_id: str,
        messages: list[dict[str, Any]],
        role_label_map: dict[str, str],
        message_to_text_fn: Callable[[dict[str, Any]], str],
        db_path: Path,
    ) -> Path:
        memory_dir = db_path.parent.parent / "work_space" / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        file_path = memory_dir / f"{now.strftime('%Y-%m-%d')}.md"
        parts: list[str] = [f"## {now.strftime('%Y-%m-%d %H:%M:%S')}  session={session_id}（强制截断记录）\n\n"]
        for msg in messages:
            label = role_label_map.get(msg.get("role", ""), msg.get("role", ""))
            parts.append(f"**{label}**: {message_to_text_fn(msg)}\n\n")
        parts.append("---\n\n")
        with open(file_path, "a", encoding="utf-8") as f:
            f.write("".join(parts))
        return file_path
