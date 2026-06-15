"""Chroma 知识库存储封装。"""

from __future__ import annotations

from typing import Any
import logging

import chromadb

from lumen_agent.application.uitls.text_splitter import Chunk
from lumen_agent.config import Settings, resolve_chroma_path


class ChromaKnowledgeStore:
    """本地持久化 Chroma 知识库。"""

    _logger = logging.getLogger(__name__)

    def __init__(self, settings: Settings) -> None:
        """初始化本地持久化客户端和 collection。"""
        # 保存配置，主要用于获取持久化目录、集合名和距离度量。
        self._settings = settings
        self._base_dir = resolve_chroma_path(settings)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        # PersistentClient 会把索引文件写入本地目录，适合知识库长期持久化。
        self._client = chromadb.PersistentClient(path=str(self._base_dir))
        self._collection = self._client.get_or_create_collection(
            name=settings.get("RAG_COLLECTION_NAME", "knowledge_base"),
            metadata={"hnsw:space": settings.get("RAG_DISTANCE_METRIC", "cosine")},
        )
        self._logger.info(
            "向量库初始化完成，目录=%s，集合=%s，距离规则=%s",
            str(self._base_dir),
            settings.get("RAG_COLLECTION_NAME", "knowledge_base"),
            settings.get("RAG_DISTANCE_METRIC", "cosine"),
        )

    async def upsert_chunks(
        self,
        *,
        knowledge_id: str,
        source_name: str,
        file_name: str,
        source_path: str | None,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
        """把 chunk 文本、向量和元数据写入 Chroma。"""
        # 以知识 ID + chunk 序号 + 起始位置拼出稳定主键，便于覆盖写入。
        ids = [f"{knowledge_id}:{chunk.chunk_index}:{chunk.start_char}" for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        metadatas: list[dict[str, Any]] = []
        for chunk in chunks:
            # 元数据用于后续追踪来源、定位原文以及做结果展示。
            metadatas.append(
                {
                    "knowledge_id": knowledge_id,
                    "source_name": source_name,
                    "file_name": file_name,
                    "source_path": source_path or "",
                    "chunk_index": chunk.chunk_index,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                }
            )
        # upsert 会在 id 已存在时覆盖，适合重复导入同一份内容。
        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        self._logger.info(
            "向量库写入完成，集合=%s，知识编号=%s，文件名=%s，块数量=%s",
            self._settings.get("RAG_COLLECTION_NAME", "knowledge_base"),
            knowledge_id,
            file_name,
            len(chunks),
        )

    async def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int,
        similarity_threshold: float,
    ) -> list[dict[str, Any]]:
        """根据 query 向量执行相似度检索，并过滤低分结果。"""
        # query_embeddings 使用已算好的 query 向量，避免再重复走 embedding。
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        rows: list[dict[str, Any]] = []
        for doc, meta, distance in zip(documents, metadatas, distances):
            # Chroma 返回的是 distance，这里转换成更易理解的 score。
            score = self._distance_to_score(distance)
            if score < similarity_threshold:
                continue
            rows.append(
                {
                    "text": doc,
                    "score": score,
                    "distance": distance,
                    "metadata": meta or {},
                }
            )
        self._logger.info(
            "向量库检索完成，集合=%s，返回条数=%s，相似度阈值=%s，命中数量=%s",
            self._settings.get("RAG_COLLECTION_NAME", "knowledge_base"),
            top_k,
            similarity_threshold,
            len(rows),
        )
        return rows

    def list_collections(self) -> list[str]:
        """列出本地已有 collection 名称。"""
        return [c.name for c in self._client.list_collections()]

    def delete_collection(self) -> None:
        """删除当前 collection，用于重建索引。"""
        self._client.delete_collection(self._settings.get("RAG_COLLECTION_NAME", "knowledge_base"))
        self._collection = self._client.get_or_create_collection(
            name=self._settings.get("RAG_COLLECTION_NAME", "knowledge_base"),
            metadata={"hnsw:space": self._settings.get("RAG_DISTANCE_METRIC", "cosine")},
        )

    def delete_knowledge(self, knowledge_id: str) -> None:
        """按 knowledge_id 删除对应 chunk。"""
        self._collection.delete(where={"knowledge_id": knowledge_id})

    @staticmethod
    def _distance_to_score(distance: float) -> float:
        """把距离值粗略归一化成 0～1 的相似度分数。"""
        return max(0.0, 1.0 - float(distance))
