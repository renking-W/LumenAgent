"""RAG 业务服务：统一封装知识入库、检索与 tool_result 组装。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import logging

from lumen_agent.application.uitls.text_splitter import Chunk, split_text_into_chunks
from lumen_agent.application.uitls.document_reader import (
    MARKITDOWN_EXTENSIONS,
    read_by_markitdown,
)
from lumen_agent.config import Settings, resolve_db_path, resolve_chroma_path
from lumen_agent.model_adapters.client.chroma_client import ChromaKnowledgeStore
from lumen_agent.model_adapters.client.embedding_client import AlibabaEmbeddingClient
from lumen_agent.infrastructure.data_base.sqlite_knowledge import SqliteKnowledgeRepository
from lumen_agent.infrastructure.data_base.knowledge_index_store import KnowledgeIndexStore


@dataclass(slots=True)
class IngestResult:
    """知识入库结果。"""

    knowledge_id: str
    source_name: str
    source_path: str | None
    chunks_added: int
    collection_name: str


@dataclass(slots=True)
class SearchResult:
    """知识检索结果。"""

    query: str
    collection_name: str
    top_k: int
    similarity_threshold: float
    chunks: list[dict[str, Any]]


class RagService:
    """共享 RAG 服务：API 与 agent 工具复用同一套实现。"""

    _logger = logging.getLogger(__name__)

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        # Embedding 客户端只负责把文本转换为向量。
        self._embedding_client = AlibabaEmbeddingClient(settings)
        # Chroma 存储封装负责持久化入库和向量检索。
        self._store = ChromaKnowledgeStore(settings)
        # SQLite 知识库仓储负责文档列表与 chunk 映射。
        self._meta_store = SqliteKnowledgeRepository(resolve_db_path(settings))
        # JSON 索引文件负责 file_name 与 source 的快速映射展示。
        self._index_store = KnowledgeIndexStore(resolve_chroma_path(settings) / "knowledge_index.json")

    async def start(self) -> None:
        """启动时初始化长连接（由工厂方法或 lifespan 调用）。"""
        await self._meta_store.open()

    async def close(self) -> None:
        """关闭长连接。"""
        await self._meta_store.close()

    async def ingest_text(
        self,
        *,
        text: str,
        source_name: str,
        file_name: str | None = None,
        source_path: str | None = None,
        knowledge_id: str | None = None,
    ) -> IngestResult:
        """将文本切分、向量化并写入知识库。"""
        # 先把原始文本拆成适合 embedding 的 chunk。
        # 这里采用“递归分隔 + 重叠”的策略，尽量保持语义完整。
        chunks = split_text_into_chunks(
            text,
            chunk_size=self._settings.get("RAG_CHUNK_SIZE", 500),
            chunk_overlap=self._settings.get("RAG_CHUNK_OVERLAP", 150),
        )
        self._logger.info(
            "知识入库：文本切分完成，来源=%s，文件名=%s，知识编号=%s，块数量=%s，文本长度=%s",
            source_name,
            file_name or source_name,
            knowledge_id or source_name,
            len(chunks),
            len(text),
        )
        return await self._ingest_chunks(
            chunks=chunks,
            source_name=source_name,
            file_name=file_name or source_name,
            source_path=source_path,
            knowledge_id=knowledge_id,
        )

    async def ingest_file(
        self,
        file_path: Path,
        *,
        knowledge_id: str | None = None,
    ) -> IngestResult:
        """读取文件后入库，特殊文档先通过 MarkItDown 转换。"""
        if file_path.suffix.lower() in MARKITDOWN_EXTENSIONS:
            text = await asyncio.to_thread(read_by_markitdown, file_path)
        else:
            text = file_path.read_text(encoding="utf-8")
        self._logger.info(
            "知识入库：文件读取完成，路径=%s，文件名=%s，内容长度=%s",
            str(file_path),
            file_path.name,
            len(text),
        )
        return await self.ingest_text(
            text=text,
            source_name=file_path.name,
            file_name=file_path.name,
            source_path=str(file_path),
            knowledge_id=knowledge_id,
        )

    async def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
    ) -> SearchResult:
        """向量检索知识库 chunk。"""
        # 若调用方不传参数，则回退到配置文件中的默认值。
        k = top_k if top_k is not None else self._settings.get("RAG_TOP_K", 5)
        threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else self._settings.get("RAG_SIMILARITY_THRESHOLD", 0.2)
        )
        self._logger.info(
            "知识检索：开始检索，查询内容=%r，返回条数=%s，相似度阈值=%s，集合=%s",
            query,
            k,
            threshold,
            self._settings.get("RAG_COLLECTION_NAME", "knowledge_base"),
        )
        # 先对 query 做 embedding，再交给 Chroma 做向量相似度检索。
        query_vector = await self._embedding_client.embed_query(query)
        raw_results = await self._store.search(
            query_vector,
            top_k=k,
            similarity_threshold=threshold,
        )
        self._logger.info(
            "知识检索：检索完成，查询内容=%r，命中块数量=%s",
            query,
            len(raw_results),
        )
        return SearchResult(
            query=query,
            collection_name=self._settings.get("RAG_COLLECTION_NAME", "knowledge_base"),
            top_k=k,
            similarity_threshold=threshold,
            chunks=raw_results,
        )

    def list_collections(self) -> list[str]:
        """列出当前可见的 collection 名称。"""
        return self._store.list_collections()

    def delete_knowledge(self, knowledge_id: str) -> None:
        """删除某个 knowledge_id 对应的所有 chunk。"""
        self._store.delete_knowledge(knowledge_id)

    async def delete_document(self, knowledge_id: str, file_name: str) -> dict[str, Any] | None:
        """删除文档元数据、向量数据与索引条目。"""
        doc = await self._meta_store.delete_document(knowledge_id, file_name)
        if doc is None:
            return None
        self._store.delete_knowledge(knowledge_id)
        removed_name = str(doc.get("file_name") or "")
        if removed_name:
            self._index_store.remove(removed_name)
        return doc

    async def list_documents(self) -> list[dict[str, Any]]:
        """列出知识库中的全部文档摘要。"""
        return await self._meta_store.list_documents()

    async def get_document(self, knowledge_id: str, file_name: str) -> dict[str, Any] | None:
        """获取某个文档及其切片详情。"""
        return await self._meta_store.get_document(knowledge_id, file_name)

    def rebuild_collection(self) -> None:
        """删除当前 collection 并重新创建，作为全量重建入口。"""
        self._store.delete_collection()

    async def _ingest_chunks(
        self,
        *,
        chunks: list[Chunk],
        source_name: str,
        file_name: str,
        source_path: str | None,
        knowledge_id: str | None,
    ) -> IngestResult:
        knowledge_id_value = knowledge_id or source_name
        index_source = source_path or "self_bulid"
        self._logger.info(
            "知识入库：开始写入元数据，来源=%s，文件名=%s，知识编号=%s，块数量=%s",
            index_source,
            file_name,
            knowledge_id_value,
            len(chunks),
        )
        # 先写 SQLite 元数据，保证文档列表和切片映射可追踪。
        await self._meta_store.create_or_reset_document(
            knowledge_id=knowledge_id_value,
            file_name=file_name,
            source_name=source_name,
            source_path=source_path,
        )
        self._index_store.upsert(file_name=file_name, source=index_source)
        # 没有可入库内容时，直接返回空结果，避免向量接口空调用。
        if not chunks:
            self._logger.info(
                "知识入库：未检测到可入库内容，来源=%s，知识编号=%s",
                source_name,
                knowledge_id or source_name,
            )
            await self._meta_store.mark_failed(knowledge_id or source_name)
            return IngestResult(
                knowledge_id=knowledge_id or source_name,
                source_name=source_name,
                source_path=source_path,
                chunks_added=0,
                collection_name=self._settings.get("RAG_COLLECTION_NAME", "knowledge_base"),
            )
        chunk_rows = [
            {
                "chunk_index": chunk.chunk_index,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "content": chunk.text,
                "content_preview": chunk.text[:200],
            }
            for chunk in chunks
        ]
        await self._meta_store.append_chunks(
            knowledge_id=knowledge_id_value,
            file_name=file_name,
            chunks=chunk_rows,
        )
        # Embedding 和 Chroma 写入属于同一入库阶段，任一步失败都标记文档失败。
        try:
            # 大文档按配置分批请求，避免一次提交过多 chunk 被向量接口拒绝。
            texts = [chunk.text for chunk in chunks]
            vectors = await self._embedding_client.embed_documents_batched(texts)
            self._logger.info(
                "知识入库：开始写入向量库，来源=%s，文件名=%s，知识编号=%s，块数量=%s，集合=%s",
                source_name,
                file_name,
                knowledge_id_value,
                len(chunks),
                self._settings.get("RAG_COLLECTION_NAME", "knowledge_base"),
            )
            # 将 chunk、向量和元信息一次性 upsert 到向量库，避免多次 IO。
            await self._store.upsert_chunks(
                knowledge_id=knowledge_id_value,
                source_name=source_name,
                file_name=file_name,
                source_path=source_path,
                chunks=chunks,
                embeddings=vectors,
            )
        except Exception:
            await self._meta_store.mark_failed(knowledge_id_value, file_name)
            raise
        return IngestResult(
            knowledge_id=knowledge_id_value,
            source_name=source_name,
            source_path=source_path,
            chunks_added=len(chunks),
            collection_name=self._settings.get("RAG_COLLECTION_NAME", "knowledge_base"),
        )
