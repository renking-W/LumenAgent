"""MCP 工具向量检索服务：ChromaDB collection + embedding 检索。

与 MemoryRagService 类似，但 metadata 携带 server_id / original_name，
便于 Agent 检索后回 SQLite 取完整 schema。
"""

from __future__ import annotations

import logging
from typing import Any

import chromadb

from lumen_agent.config import Settings, resolve_chroma_path
from lumen_agent.model_adapters.client.embedding_client import AlibabaEmbeddingClient

_COLLECTION_NAME = "mcp_tools_store"


class McpToolRagService:
    """MCP 工具向量检索服务。"""

    _logger = logging.getLogger(__name__)

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._embedding_client = AlibabaEmbeddingClient(settings)
        self._base_dir = resolve_chroma_path(settings)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self._base_dir))
        collection_name = settings.get("MCP_TOOL_COLLECTION_NAME", _COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    async def upsert_tool(
        self,
        tool_id: str,
        search_doc: str,
        metadata: dict[str, Any],
    ) -> None:
        """写入或覆盖单条 tool 向量（id 与 SQLite mcp_tools.id 一致）。"""
        embedding = await self._embedding_client.embed_query(search_doc)
        self._collection.upsert(
            ids=[tool_id],
            documents=[search_doc],
            metadatas=[metadata],
            embeddings=[embedding],
        )

    def delete_tools(self, tool_ids: list[str]) -> None:
        """按 tool_id 删除向量（server 禁用/删除或 sync 清理 stale 时调用）。"""
        if not tool_ids:
            return
        self._collection.delete(ids=tool_ids)

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
        server_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """向量检索 MCP 工具，返回 tool_id + score（不含完整 schema）。"""
        query_vector = await self._embedding_client.embed_query(query)

        # 可选：限定在前端选中的 MCP Server 范围内检索
        where: dict[str, Any] | None = None
        if server_ids is not None:
            if not server_ids:
                return []
            where = {"server_id": {"$in": server_ids}}

        result = self._collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
            where=where,
        )
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        rows: list[dict[str, Any]] = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            # cosine distance → 相似度分数（0~1，越大越相似）
            score = max(0.0, 1.0 - float(dist))
            if score < similarity_threshold:
                continue
            rows.append({
                "tool_id": (meta or {}).get("tool_id", ""),
                "text": doc,
                "score": round(score, 4),
                "distance": round(float(dist), 4),
                "metadata": meta or {},
            })
        self._logger.info(
            "MCP 工具检索完成：query=%r top_k=%s hits=%s",
            query,
            top_k,
            len(rows),
        )
        return rows
