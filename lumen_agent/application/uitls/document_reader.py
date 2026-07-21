"""特殊文档读取：使用 MarkItDown 将本地文件转换为 Markdown。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


MARKITDOWN_EXTENSIONS = frozenset(
    {".csv", ".docx", ".xlsx", ".doc", ".pptx", ".ppt", ".pdf"}
)


class DocumentReadError(RuntimeError):
    """本地文档无法通过 MarkItDown 读取。"""


@lru_cache(maxsize=32)
def _convert_cached(path: str, modified_ns: int, size: int) -> str:
    """按文件状态缓存转换结果，文件变化后自动生成新缓存项。"""
    del modified_ns, size
    try:
        from markitdown import MarkItDown
    except ImportError as exc:
        raise DocumentReadError("MarkItDown 未安装，请先安装项目依赖。") from exc

    try:
        result = MarkItDown(enable_plugins=False).convert_local(path)
    except Exception as exc:
        raise DocumentReadError(f"MarkItDown 无法解析该文件：{exc}") from exc

    text = result.text_content
    if not text.strip():
        raise DocumentReadError("MarkItDown 未从该文件中提取到可读取内容。")
    return text


def read_by_markitdown(file_path: Path) -> str:
    """校验本地文件后，通过 MarkItDown 返回 Markdown 文本。"""
    path = file_path.expanduser().resolve()
    if not path.exists():
        raise DocumentReadError(f"文件不存在：{path}")
    if not path.is_file():
        raise DocumentReadError(f"路径不是普通文件：{path}")
    if path.suffix.lower() not in MARKITDOWN_EXTENSIONS:
        supported = ", ".join(sorted(MARKITDOWN_EXTENSIONS))
        raise DocumentReadError(
            f"read_by_markdown 不支持 {path.suffix or '无扩展名文件'}，支持：{supported}"
        )

    stat = path.stat()
    return _convert_cached(str(path), stat.st_mtime_ns, stat.st_size)
