"""知识库 API DTO。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeIngestRequest(BaseModel):
    """知识入库请求体。"""

    text: str | None = None
    file_path: str | None = None
    source_name: str | None = None
    knowledge_id: str | None = None


class KnowledgeSearchRequest(BaseModel):
    """知识检索请求体。"""

    query: str = Field(min_length=1)
    top_k: int | None = None
    similarity_threshold: float | None = None


class KnowledgeIngestResponse(BaseModel):
    """知识入库响应体。"""

    knowledge_id: str
    source_name: str
    source_path: str | None = None
    chunks_added: int
    collection_name: str


class KnowledgeSearchChunk(BaseModel):
    """知识检索 chunk 响应项。"""

    text: str
    score: float
    distance: float
    metadata: dict


class KnowledgeSearchResponse(BaseModel):
    """知识检索响应体。"""

    query: str
    collection_name: str
    top_k: int
    similarity_threshold: float
    chunks: list[KnowledgeSearchChunk]


class KnowledgeDocumentSummary(BaseModel):
    knowledge_id: str
    file_name: str
    source_name: str
    source_path: str | None = None
    status: str
    chunk_count: int
    created_at: str
    updated_at: str


class KnowledgeChunkDetail(BaseModel):
    chunk_index: int
    start_char: int
    end_char: int
    content: str
    content_preview: str
    created_at: str
    file_name: str


class KnowledgeDocumentDetail(BaseModel):
    knowledge_id: str
    file_name: str
    source_name: str
    source_path: str | None = None
    status: str
    chunk_count: int
    created_at: str
    updated_at: str
    chunks: list[KnowledgeChunkDetail]
