"""知识库索引文件：维护 file_name 与 source 的映射。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class KnowledgeIndexStore:
    """管理 knowledge_index.json 的轻量索引存储。"""

    def __init__(self, index_path: Path) -> None:
        self._index_path = index_path
        self._index_path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[dict[str, Any]]:
        """读取索引文件，文件不存在时返回空列表。"""
        if not self._index_path.exists():
            return []
        raw = self._index_path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        return json.loads(raw)

    def _write(self, items: list[dict[str, Any]]) -> None:
        """写回索引文件。"""
        self._index_path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def upsert(self, *, file_name: str, source: str) -> None:
        """新增或更新一个 file_name → source 映射。"""
        items = self._read()
        items = [item for item in items if item.get("file_name") != file_name]
        items.append({"file_name": file_name, "source": source})
        self._write(items)

    def remove(self, file_name: str) -> None:
        """删除一个 file_name 对应的映射。"""
        items = self._read()
        items = [item for item in items if item.get("file_name") != file_name]
        self._write(items)

    def list_items(self) -> list[dict[str, Any]]:
        """列出所有映射。"""
        return self._read()
