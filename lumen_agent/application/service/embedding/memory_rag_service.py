"""记忆向量检索服务：只做 embedding + ChromaDB 检索，不写 SQLite。

与知识库 RAG（RagService）的区别：
- 不维护 SQLite 元数据，不用 JSON 索引
- 纯向量化 + ChromaDB 按条目存储 + 检索
- 按 `## ... session=xxx` 块作为独立记忆条目
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb

from lumen_agent.agent.memory.memory_utils import MemoryFileUtils
from lumen_agent.config import Settings, resolve_chroma_path
from lumen_agent.model_adapters.client.embedding_client import AlibabaEmbeddingClient

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

    def _existing_hashes(self, entry_ids: list[str]) -> dict[str, str]:
        """批量读取 Chroma 中记忆条目对应的内容指纹。"""
        if not entry_ids:
            return {}
        result = self._collection.get(ids=entry_ids, include=["metadatas"])
        ids = result.get("ids") or []
        metadatas = result.get("metadatas") or []
        return {
            str(entry_id): str((metadata or {}).get("content_hash", ""))
            for entry_id, metadata in zip(ids, metadatas)
        }

    async def _upsert_entries(
        self,
        entries: list[tuple[str, str, dict[str, Any], str]],
    ) -> int:
        """批量向量化并覆盖写入已经确认发生变化的记忆条目。"""
        if not entries:
            return 0
        embeddings = await self._embedding_client.embed_documents_batched(
            [entry_text for _, entry_text, _, _ in entries]
        )
        if len(embeddings) != len(entries):
            raise RuntimeError("embedding response count does not match memory entry count")

        metadatas: list[dict[str, Any]] = []
        for _, _, metadata, content_hash in entries:
            stored_metadata = dict(metadata)
            stored_metadata["content_hash"] = content_hash
            stored_metadata["embedding_model"] = self._embedding_client.model_name
            metadatas.append(stored_metadata)

        self._collection.upsert(
            ids=[entry_id for entry_id, _, _, _ in entries],
            documents=[entry_text for _, entry_text, _, _ in entries],
            metadatas=metadatas,
            embeddings=embeddings,
        )
        return len(entries)

    async def index_entry(
        self,
        entry_text: str,
        entry_id: str,
        metadata: dict[str, Any],
    ) -> None:
        """索引单条记忆；内容和模型未变化时直接复用已有向量。"""
        content_hash = self._embedding_client.content_hash(entry_text)
        existing_hash = self._existing_hashes([entry_id]).get(entry_id)
        if existing_hash == content_hash:
            return
        await self._upsert_entries(
            [(entry_id, entry_text, metadata, content_hash)]
        )
        self._logger.debug("记忆条目已索引：%s", entry_id)

    _CHECKPOINT_VERSION = 2

    # ── Checkpoint 持久化 ─────────────────────────────────────────

    def _empty_checkpoint(self) -> dict[str, Any]:
        """返回与当前向量模型绑定的空 checkpoint。"""
        return {
            "version": self._CHECKPOINT_VERSION,
            "embedding_model": self._embedding_client.model_name,
            "files": {},
        }

    def _load_checkpoint(self) -> dict[str, Any]:
        """加载索引 checkpoint；版本或向量模型变化时强制重新核对。"""
        path = self._base_dir / "memory_index_checkpoint.json"
        if not path.exists():
            return self._empty_checkpoint()
        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            if (
                data.get("version") != self._CHECKPOINT_VERSION
                or data.get("embedding_model") != self._embedding_client.model_name
            ):
                return self._empty_checkpoint()
            return data
        except (json.JSONDecodeError, OSError):
            return self._empty_checkpoint()

    def _save_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        """持久化文件内容指纹、条目 ID 和向量模型。"""
        path = self._base_dir / "memory_index_checkpoint.json"
        checkpoint["version"] = self._CHECKPOINT_VERSION
        checkpoint["embedding_model"] = self._embedding_client.model_name
        checkpoint["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            path.write_text(
                json.dumps(checkpoint, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            self._logger.warning("无法写入记忆索引 checkpoint", exc_info=True)

    @staticmethod
    def _file_content_hash(file_path: Path) -> str | None:
        """读取文件内容并计算 SHA256，文件不可读时返回 None。"""
        try:
            return hashlib.sha256(file_path.read_bytes()).hexdigest()
        except OSError:
            return None

    async def index_all_memory_files(self, memory_utils: MemoryFileUtils) -> None:
        """扫描每日记忆文件，仅向量化新增或内容发生变化的条目。"""
        memory_dir = memory_utils.memory_dir
        if not memory_dir.exists():
            self._logger.warning("记忆目录不存在：%s", memory_dir)
            return

        md_files = sorted(
            path for path in memory_dir.glob("*.md") if path.name != "MEMORY.md"
        )
        if not md_files:
            self._logger.info("没有找到每日记忆文件，跳过全量索引")


        checkpoint = self._load_checkpoint()
        file_records: dict[str, dict[str, Any]] = checkpoint.get("files", {})
        current_file_names = {path.name for path in md_files}
        expected_entry_ids: set[str] = set()

        pending_entries: list[tuple[str, str, dict[str, Any], str]] = []
        stale_entry_ids: list[str] = []
        skipped_entry_count = 0
        skipped_file_count = 0
        records_changed = False

        # 文件已经删除时，同步清理 checkpoint 和对应 Chroma 条目。
        for removed_name in set(file_records) - current_file_names:
            stale_entry_ids.extend(file_records[removed_name].get("entry_ids", []))
            file_records.pop(removed_name, None)
            records_changed = True

        for md_file in md_files:
            file_hash = self._file_content_hash(md_file)
            if file_hash is None:
                continue

            last = file_records.get(md_file.name)
            if last is not None and last.get("content_hash") == file_hash:
                expected_entry_ids.update(last.get("entry_ids", []))
                skipped_file_count += 1
                continue

            content = md_file.read_text(encoding="utf-8")
            entries = self._parse_daily_file(content, md_file.stem)
            current_entry_ids = [entry_id for entry_id, _, _ in entries]
            expected_entry_ids.update(current_entry_ids)
            existing_hashes = self._existing_hashes(current_entry_ids)

            for entry_id, entry_text, metadata in entries:
                content_hash = self._embedding_client.content_hash(entry_text)
                if existing_hashes.get(entry_id) == content_hash:
                    skipped_entry_count += 1
                    continue
                pending_entries.append(
                    (entry_id, entry_text, metadata, content_hash)
                )

            previous_entry_ids = set((last or {}).get("entry_ids", []))
            stale_entry_ids.extend(previous_entry_ids - set(current_entry_ids))
            file_records[md_file.name] = {
                "content_hash": file_hash,
                "entry_ids": current_entry_ids,
            }
            records_changed = True

        # 以当前全部文件为准做一次本地 ID 对账，兼容 checkpoint 升级和文件全部删除。
        existing_result = self._collection.get()
        existing_entry_ids = {str(item) for item in (existing_result.get("ids") or [])}
        stale_entry_ids.extend(existing_entry_ids - expected_entry_ids)

        if stale_entry_ids:
            self._collection.delete(ids=sorted(set(stale_entry_ids)))

        indexed_count = await self._upsert_entries(pending_entries)

        if records_changed:
            checkpoint["files"] = file_records
            self._save_checkpoint(checkpoint)

        self._logger.info(
            "记忆增量索引完成：新增或更新 %s 条，跳过 %s 条，跳过 %s 个未变更文件，删除 %s 条",
            indexed_count,
            skipped_entry_count,
            skipped_file_count,
            len(set(stale_entry_ids)),
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
