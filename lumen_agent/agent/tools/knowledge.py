"""Knowledge 工具：知识插入与检索。"""

from __future__ import annotations

from pathlib import Path
import logging

from lumen_agent.agent.tools.base import BaseTool, ToolResult
from lumen_agent.agent.tools.registry import ToolRegistry
from lumen_agent.application.service.rag_service import RagService
from lumen_agent.config import get_settings


@ToolRegistry.register
class KnowledgeSearch(BaseTool):
    """在知识库中按 query 检索最相关的 chunk。"""

    _logger = logging.getLogger(__name__)

    name = "knowledge_search"
    description = "在知识库中检索与 query 最相关的 chunk，返回来源、相似度和 chunk 内容。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "要检索的自然语言问题或关键词。"},
            "top_k": {"type": "integer", "description": "返回的最大 chunk 数。可选。"},
            "similarity_threshold": {"type": "number", "description": "相似度阈值，低于该值的 chunk 将被过滤。可选。"},
        },
        "required": ["query"],
    }

    async def execute(self, params: dict) -> ToolResult:
        """执行知识检索并返回标准化 tool_result。"""
        query = str(params.get("query", "")).strip()
        if not query:
            return ToolResult.error("query 不能为空。")

        settings = get_settings()
        # 工具层不自己实现检索逻辑，而是复用共享的 RAG 服务。
        service = RagService(settings)
        self._logger.info(
            "知识检索工具：开始检索，查询内容=%r，返回条数=%s，相似度阈值=%s",
            query,
            params.get("top_k"),
            params.get("similarity_threshold"),
        )
        result = await service.search(
            query,
            top_k=params.get("top_k"),
            similarity_threshold=params.get("similarity_threshold"),
        )
        # 将检索结果整理成 tool_result，便于模型直接消费和上层落库。
        payload = {
            "query": result.query,
            "collection_name": result.collection_name,
            "top_k": result.top_k,
            "similarity_threshold": result.similarity_threshold,
            "chunks": result.chunks,
        }
        self._logger.info(
            "知识检索工具：检索完成，命中块数量=%s，集合=%s",
            len(result.chunks),
            result.collection_name,
        )
        return ToolResult.success(payload)


@ToolRegistry.register
class KnowledgeInsert(BaseTool):
    """将文本或文件入库到知识库。"""

    name = "knowledge_insert"
    description = "将文本或文件入库到知识库，自动切分、embedding 并写入 Chroma。"
    requires_approval = True
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "待入库的文本内容。与 file_path 二选一。"},
            "file_path": {"type": "string", "description": "待入库文件路径。与 text 二选一。"},
            "source_name": {"type": "string", "description": "来源名称，可选。"},
            "knowledge_id": {"type": "string", "description": "知识条目标识，可选。"},
        },
        "required": [],
    }

    async def execute(self, params: dict) -> ToolResult:
        """执行知识入库并返回标准化 tool_result。"""
        text = str(params.get("text", "")).strip()
        file_path_value = str(params.get("file_path", "")).strip()
        if not text and not file_path_value:
            return ToolResult.error("text 和 file_path 至少提供一个。")

        settings = get_settings()
        # 入库也复用同一套 RAG 服务，避免 API 场景和工具场景逻辑分叉。
        service = RagService(settings)
        self._logger.info(
            "知识入库工具：开始入库，文本长度=%s，文件路径=%s，知识编号=%s",
            len(text),
            file_path_value or None,
            params.get("knowledge_id"),
        )
        if file_path_value:
            # 文件路径场景：交给共享服务读取文件并完成整个入库流程。
            result = await service.ingest_file(Path(file_path_value), knowledge_id=params.get("knowledge_id"))
        else:
            # 文本场景：直接用用户传入的 text 入库。
            source_name = str(params.get("source_name") or params.get("knowledge_id") or "manual_input")
            result = await service.ingest_text(
                text=text,
                source_name=source_name,
                knowledge_id=params.get("knowledge_id"),
            )
        # 返回统一结构，供 LLM 和上层逻辑解析。
        payload = {
            "knowledge_id": result.knowledge_id,
            "source_name": result.source_name,
            "source_path": result.source_path,
            "chunks_added": result.chunks_added,
            "collection_name": result.collection_name,
        }
        self._logger.info(
            "知识入库工具：入库完成，块数量=%s，集合=%s",
            result.chunks_added,
            result.collection_name,
        )
        return ToolResult.success(payload)
