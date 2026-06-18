"""记忆文件服务：记忆文件读取、ChromaDB 重索引等非 HTTP 编排逻辑。"""

from __future__ import annotations

import logging

import chromadb

from lumen_agent.agent.memory.memory_utils import MemoryFileUtils
from lumen_agent.api.schemas.memory_dtos import MemoryFileItem
from lumen_agent.application.service.memory_rag_service import MemoryRagService
from lumen_agent.application.uitls.dir_guide import DirGuide
from lumen_agent.config import Settings, resolve_chroma_path

logger = logging.getLogger(__name__)

# 定位 work_space/memory 目录（与 builder.py 保持一致）
_WORKSPACE_DIR = DirGuide.workspace_dir()
_MEMORY_UTILS = MemoryFileUtils.from_workspace_path(_WORKSPACE_DIR)


def list_memory_files() -> list[MemoryFileItem]:
    """读取所有记忆文件内容，包括 MEMORY.md 和所有每日记忆文件。"""
    memory_dir = _MEMORY_UTILS.memory_dir
    if not memory_dir.exists():
        logger.warning("记忆目录不存在：%s", memory_dir)
        return []

    items: list[MemoryFileItem] = []

    # 1) MEMORY.md - 长期记忆（优先 memory 子目录，兼容旧路径 workspace 根目录）
    memory_path = _MEMORY_UTILS.memory_file_path()
    if not memory_path.exists():
        memory_path = _WORKSPACE_DIR / "MEMORY.md"
    if memory_path.exists():
        content = memory_path.read_text(encoding="utf-8")
        items.append(MemoryFileItem(file_name="MEMORY.md", content=content, type="long_term"))
        logger.debug("读取记忆文件：%s (%d 字符)", memory_path, len(content))

    # 2) 每日记忆文件 (YYYY-MM-DD.md)
    for md_file in sorted(memory_dir.glob("*.md")):
        if md_file.name == "MEMORY.md":
            continue
        content = md_file.read_text(encoding="utf-8")
        items.append(MemoryFileItem(file_name=md_file.name, content=content, type="daily"))
        logger.debug("读取记忆文件：%s (%d 字符)", md_file.name, len(content))

    logger.info(
        "读取记忆文件完成：MEMORY.md + %s 个每日文件，共 %s 个文件",
        len(items) - (1 if items and items[0].type == "long_term" else 0),
        len(items),
    )
    return items


async def reindex_memory_files(settings: Settings) -> dict:
    """强制全量重索引记忆文件：清空 ChromaDB + checkpoint 后重新向量化所有记忆条目。"""
    chroma_dir = resolve_chroma_path(settings)
    checkpoint_path = chroma_dir / "memory_index_checkpoint.json"

    # 1) 删除 checkpoint
    if checkpoint_path.exists():
        checkpoint_path.unlink()
        logger.info("已删除 memory_index_checkpoint.json")

    # 2) 删除 ChromaDB 中的 memory_store collection
    client = chromadb.PersistentClient(path=str(chroma_dir))
    try:
        client.delete_collection("memory_store")
        logger.info("已删除 ChromaDB memory_store collection")
    except ValueError:
        logger.warning("ChromaDB memory_store collection 不存在，将新建")

    # 3) 全量重新索引
    service = MemoryRagService(settings)
    await service.index_all_memory_files(_MEMORY_UTILS)

    # 重新索引后统计条目数
    new_collection = client.get_collection("memory_store")
    total = new_collection.count()
    logger.info("记忆全量重索引完成，当前 memory_store 条目数: %s", total)

    return {
        "status": "ok",
        "message": f"记忆全量重索引完成，共 {total} 条",
        "total_entries": total,
    }
