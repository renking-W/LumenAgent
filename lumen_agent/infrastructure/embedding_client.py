"""阿里云 Embedding 客户端：`text-embedding-v4`。"""

from __future__ import annotations

from typing import Any

import httpx

from lumen_agent.config import Settings


class AlibabaEmbeddingClient:
    """阿里云 text-embedding-v4 客户端封装。"""

    def __init__(self, settings: Settings) -> None:
        # 保存配置，供后续拼接请求地址、鉴权和模型名称使用。
        self._settings = settings

    def _headers(self) -> dict[str, str]:
        """构造 embedding 请求头。"""
        api_key = self._settings.embedding_api_key.strip()
        if not api_key:
            # 这里不要继续拼接 Bearer 空值，否则 httpx 会直接判定 header 非法。
            raise RuntimeError("EMBEDDING_API_KEY is not configured")
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量把文本转换为向量。"""
        if not texts:
            return []
        # 按阿里云兼容接口要求组装请求体。
        payload = {"model": self._settings.embedding_model, "input": texts}
        data = await self._post(payload)
        return self._extract_embeddings(data)

    async def embed_query(self, text: str) -> list[float]:
        """把单个 query 文本转换为向量。"""
        embeddings = await self.embed_documents([text])
        if not embeddings:
            raise RuntimeError("embedding response is empty")
        return embeddings[0]

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        """发送 HTTP 请求到 embedding 服务。"""
        url = self._settings.embedding_base_url.rstrip("/")
        timeout = httpx.Timeout(120.0, connect=10.0)
        # 使用异步客户端发请求，避免阻塞事件循环。
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=self._headers(), json=payload)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _extract_embeddings(data: dict[str, Any]) -> list[list[float]]:
        """从返回 JSON 中提取向量列表。"""
        items = data.get("data") or []
        embeddings: list[list[float]] = []
        for item in items:
            emb = item.get("embedding")
            if isinstance(emb, list):
                embeddings.append([float(v) for v in emb])
        return embeddings
