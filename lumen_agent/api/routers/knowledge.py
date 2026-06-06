"""知识库路由：入库、检索、列表、删除/重建。"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from lumen_agent.api.dependency import get_settings
from lumen_agent.api.schemas.knowledge_dtos import (
    KnowledgeChunkDetail,
    KnowledgeDocumentDetail,
    KnowledgeDocumentSummary,
    KnowledgeIngestRequest,
    KnowledgeIngestResponse,
    KnowledgeSearchChunk,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from lumen_agent.application.service.rag_service import RagService
from lumen_agent.config import Settings

router = APIRouter(prefix="/v1/knowledge", tags=["knowledge"])
_logger = logging.getLogger(__name__)


_rag_service: RagService | None = None


async def _get_service(settings: Settings) -> RagService:
    """获取共享的 RAG 服务单例（首次调用时初始化长连接）。"""
    global _rag_service  # noqa: PLW0603
    if _rag_service is None:
        svc = RagService(settings)
        await svc.start()
        _rag_service = svc
    return _rag_service


async def _close_rag_service() -> None:
    """关闭 RAG 服务长连接（应用关闭时调用）。"""
    global _rag_service  # noqa: PLW0603
    svc = _rag_service
    _rag_service = None
    if svc is not None:
        await svc.close()


@router.post("/ingest", response_model=KnowledgeIngestResponse)
async def ingest_knowledge(
    body: KnowledgeIngestRequest,
    settings: Settings = Depends(get_settings),
) -> KnowledgeIngestResponse:
    """API 场景下执行知识入库，支持文本或文件路径。"""
    if not body.text and not body.file_path:
        raise HTTPException(status_code=400, detail="text 和 file_path 至少提供一个")

    service = await _get_service(settings)
    _logger.info(
        "知识库接口：收到入库请求，来源名称=%s，知识编号=%s，文件路径=%s，文本长度=%s",
        body.source_name,
        body.knowledge_id,
        body.file_path,
        len(body.text or ""),
    )
    if body.file_path:
        # 文件路径场景：统一交给共享服务读取文件并完成入库。
        result = await service.ingest_file(Path(body.file_path), knowledge_id=body.knowledge_id)
    else:
        # 文本场景：直接把用户输入交给共享服务处理。
        source_name = body.source_name or body.knowledge_id or "manual_input"
        result = await service.ingest_text(
            text=body.text or "",
            source_name=source_name,
            knowledge_id=body.knowledge_id,
        )
    _logger.info(
        "知识库接口：入库完成，知识编号=%s，块数量=%s，集合=%s",
        result.knowledge_id,
        result.chunks_added,
        result.collection_name,
    )
    return KnowledgeIngestResponse(
        knowledge_id=result.knowledge_id,
        source_name=result.source_name,
        source_path=result.source_path,
        chunks_added=result.chunks_added,
        collection_name=result.collection_name,
    )


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    body: KnowledgeSearchRequest,
    settings: Settings = Depends(get_settings),
) -> KnowledgeSearchResponse:
    """API 场景下按 query 检索知识库 chunk。"""
    service = await _get_service(settings)
    _logger.info(
        "知识库接口：收到检索请求，查询内容=%r，返回条数=%s，相似度阈值=%s",
        body.query,
        body.top_k,
        body.similarity_threshold,
    )
    result = await service.search(
        body.query,
        top_k=body.top_k,
        similarity_threshold=body.similarity_threshold,
    )
    # 将服务层返回的结构化 chunk 转成 API DTO。
    chunks = [KnowledgeSearchChunk(**chunk) for chunk in result.chunks]
    _logger.info(
        "知识库接口：检索完成，查询内容=%r，命中数量=%s，集合=%s",
        body.query,
        len(chunks),
        result.collection_name,
    )
    return KnowledgeSearchResponse(
        query=result.query,
        collection_name=result.collection_name,
        top_k=result.top_k,
        similarity_threshold=result.similarity_threshold,
        chunks=chunks,
    )


@router.get("/collections")
async def list_collections(settings: Settings = Depends(get_settings)) -> dict:
    """列出当前本地已有的 Chroma collections。"""
    service = await _get_service(settings)
    collections = service.list_collections()
    _logger.info("知识库接口：查询集合列表完成，集合数量=%s", len(collections))
    return {"collections": collections}


@router.delete("/rebuild")
async def rebuild_knowledge(settings: Settings = Depends(get_settings)) -> dict:
    """重建知识库索引：删除当前 collection 并重新创建。"""
    service = await _get_service(settings)
    _logger.info("知识库接口：收到重建请求，集合=%s", settings.rag_collection_name)
    service.rebuild_collection()
    _logger.info("知识库接口：重建完成，集合=%s", settings.rag_collection_name)
    return {"detail": "rebuild ok", "collection_name": settings.rag_collection_name}


@router.delete("/{knowledge_id}/{file_name}")
async def delete_knowledge(
    knowledge_id: str,
    file_name: str,
    settings: Settings = Depends(get_settings),
) -> dict:
    """删除指定 knowledge_id 和 file_name 的索引数据。"""
    service = await _get_service(settings)
    _logger.info("知识库接口：收到删除请求，知识编号=%s，文件名=%s", knowledge_id, file_name)
    deleted = await service.delete_document(knowledge_id, file_name)
    if deleted is None:
        raise HTTPException(status_code=404, detail="知识文档不存在")
    _logger.info("知识库接口：删除完成，知识编号=%s，文件名=%s", knowledge_id, file_name)
    return {"knowledge_id": knowledge_id, "file_name": file_name, "detail": "delete ok"}


@router.get("/documents", response_model=list[KnowledgeDocumentSummary])
async def list_documents(settings: Settings = Depends(get_settings)) -> list[KnowledgeDocumentSummary]:
    """列出当前知识库中的所有文档。"""
    service = await _get_service(settings)
    docs = await service.list_documents()
    _logger.info("知识库接口：查询文档列表完成，文档数量=%s", len(docs))
    return [KnowledgeDocumentSummary(**doc) for doc in docs]


@router.get("/documents/{knowledge_id}/{file_name}", response_model=KnowledgeDocumentDetail)
async def get_document_detail(
    knowledge_id: str,
    file_name: str,
    settings: Settings = Depends(get_settings),
) -> KnowledgeDocumentDetail:
    """查看某个文档及其所有切片详情。"""
    service = await _get_service(settings)
    doc = await service.get_document(knowledge_id, file_name)
    if doc is None:
        raise HTTPException(status_code=404, detail="知识文档不存在")
    chunks = [KnowledgeChunkDetail(**chunk) for chunk in doc.pop("chunks", [])]
    _logger.info("知识库接口：查询文档详情完成，知识编号=%s，文件名=%s，块数量=%s", knowledge_id, file_name, len(chunks))
    return KnowledgeDocumentDetail(**doc, chunks=chunks)
