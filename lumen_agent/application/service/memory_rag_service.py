"""记忆向量检索服务：只做 embedding + ChromaDB 检索，不写 SQLite。

与知识库 RAG（RagService）的区别：
- 不维护 SQLite 元数据，不用 JSON 索引
- 纯向量化 + ChromaDB 按条目存储 + 检索
- 按 `## ... session=xxx` 块作为独立记忆条目
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb

from lumen_agent.agent.memory.memory_utils import MemoryFileUtils
from lumen_agent.config import Settings, resolve_chroma_path
from lumen_agent.infrastructure.client.embedding_client import AlibabaEmbeddingClient

_COLLECTION_NAME = "memory_store"


class MemoryRagService:
    """记忆向量检索服务。"""

    _logger = logging.getLogger(__name__)

    def __init__(self, settings: Settings) -> None:
        # 复用与知识库相同的 Embedding 客户端
        self._embedding_client = AlibabaEmbeddingClient(settings)
        # 共享 ChromaDB 持久化目录，使用独立的 collection
        self._base_dir = resolve_chroma_path(settings)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self._base_dir))
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        """向量检索历史记忆条目。

        参数:
            similarity_threshold: 相似度阈值，低于该值的条目将被过滤。默认 0.0 表示不过滤。
        """
        query_vector = await self._embedding_client.embed_query(query)
        result = self._collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        raw_count = 0
        rows: list[dict[str, Any]] = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            raw_count += 1
            score = max(0.0, 1.0 - float(dist))
            if score < similarity_threshold:
                continue
            rows.append({
                "text": doc,
                "score": round(score, 4),
                "distance": round(dist, 4),
                "metadata": meta or {},
            })
        self._logger.info(
            "记忆检索完成：query=%r  top_k=%s  raw=%s  threshold=%.2f  hits=%s",
            query, top_k, raw_count, similarity_threshold, len(rows),
        )
        return rows

    async def index_entry(
        self,
        entry_text: str,
        entry_id: str,
        metadata: dict[str, Any],
    ) -> None:
        """索引单条记忆条目到 ChromaDB。"""
        embedding = await self._embedding_client.embed_query(entry_text)
        self._collection.upsert(
            ids=[entry_id],
            documents=[entry_text],
            metadatas=[metadata],
            embeddings=[embedding],
        )
        self._logger.debug("记忆条目已索引：%s", entry_id)

    _CHECKPOINT_VERSION = 1

    # ── Checkpoint 持久化 ─────────────────────────────────────────

    def _load_checkpoint(self) -> dict[str, Any]:
        """加载索引 checkpoint。"""
        path = self._base_dir / "memory_index_checkpoint.json"
        if not path.exists():
            return {"version": self._CHECKPOINT_VERSION, "files": {}}
        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            if data.get("version") != self._CHECKPOINT_VERSION:
                return {"version": self._CHECKPOINT_VERSION, "files": {}}
            return data
        except (json.JSONDecodeError, OSError):
            return {"version": self._CHECKPOINT_VERSION, "files": {}}

    def _save_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        """持久化索引 checkpoint。"""
        path = self._base_dir / "memory_index_checkpoint.json"
        checkpoint["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            path.write_text(
                json.dumps(checkpoint, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            self._logger.warning("无法写入记忆索引 checkpoint", exc_info=True)

    @staticmethod
    def _file_signature(file_path: Path) -> dict[str, float | int] | None:
        """返回文件的 mtime + size 签名，文件不存在时返回 None。"""
        try:
            stat = file_path.stat()
            return {"mtime": stat.st_mtime, "size": stat.st_size}
        except OSError:
            return None

    async def index_all_memory_files(self, memory_utils: MemoryFileUtils) -> None:
        """全量扫描所有每日记忆文件，通过 checkpoint 跳过未变更文件后索引到 ChromaDB。

        利用 ChromaDB upsert 的幂等性：已存在的条目按相同 ID 覆盖（无副作用），
        新条目自动补入。首次启动会全量索引，后续仅处理新增或修改过的文件。
        """
        memory_dir = memory_utils.memory_dir
        if not memory_dir.exists():
            self._logger.warning("记忆目录不存在：%s", memory_dir)
            return

        md_files = sorted(memory_dir.glob("*.md"))
        if not md_files:
            self._logger.info("没有找到每日记忆文件，跳过全量索引")
            return

        checkpoint = self._load_checkpoint()
        file_records: dict[str, dict[str, Any]] = checkpoint.get("files", {})
        changed = False

        indexed_count = 0
        skipped_entry_count = 0
        skipped_file_count = 0

        for md_file in md_files:
            if md_file.name == "MEMORY.md":
                continue

            sig = self._file_signature(md_file)
            if sig is None:
                continue

            last = file_records.get(md_file.name)
            if last is not None and last.get("mtime") == sig["mtime"] and last.get("size") == sig["size"]:
                skipped_file_count += 1
                continue

            # 文件有变更或新增 → 重新解析并索引
            content = md_file.read_text(encoding="utf-8")
            date_str = md_file.stem
            entries = self._parse_daily_file(content, date_str)
            for entry_id, entry_text, metadata in entries:
                existing = self._collection.get(ids=[entry_id])
                if existing and existing.get("ids") and existing["ids"]:
                    skipped_entry_count += 1
                    continue
                await self.index_entry(entry_text, entry_id, metadata)
                indexed_count += 1

            file_records[md_file.name] = sig  # type: ignore[assignment]
            changed = True

        if changed:
            checkpoint["files"] = file_records
            self._save_checkpoint(checkpoint)

        self._logger.info(
            "全量记忆索引完成：新增 %s 条，跳过 %s 条（已存在），跳过 %s 个文件（未变更）",
            indexed_count, skipped_entry_count, skipped_file_count,
        )

    @staticmethod
    def _parse_daily_file(
        content: str,
        date_str: str,
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """解析每日记忆文件，按 ``---`` 分隔 + ``## ... session=xxx`` 切分为独立条目。

        返回列表，每个元素为 ``(entry_id, entry_text, metadata)``。
        """
        entries: list[tuple[str, str, dict[str, Any]]] = []
        blocks = re.split(r"\n---+\n", content)
        for block in blocks:
            block = block.strip()
            if not block:
                continue

            lines = block.split("\n")
            header = lines[0].strip()
            body = "\n".join(lines[1:]).strip()

            # 解析 header: "## YYYY-MM-DD HH:MM[:SS]  session=xxx"
            # 注意：兼容旧数据中「17:44」这种无秒数的时间戳
            m = re.match(
                r"^##\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?)\s+session=(\S+)",
                header,
            )
            if not m:
                continue

            timestamp = m.group(1)
            session_id = m.group(2)

            # 构建唯一 ID：daily:{date}:{timestamp_safe}:{session_id}
            ts_safe = timestamp.replace(":", "-").replace(" ", "_")
            entry_id = f"daily:{date_str}:{ts_safe}:{session_id}"
            metadata: dict[str, Any] = {
                "source": "daily",
                "date": date_str,
                "session_id": session_id,
                "timestamp": timestamp,
            }
            entries.append((entry_id, block, metadata))

        return entries
