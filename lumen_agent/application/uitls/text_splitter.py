"""文档切分：递归分隔 + 固定重叠。"""

from __future__ import annotations

from dataclasses import dataclass


_DEFAULT_SEPARATORS = ["\n\n", "\n", "。", "！", "？", ".", "!", "?", " "]


@dataclass(slots=True)
class Chunk:
    """切分后的 chunk 元数据。"""

    text: str
    start_char: int
    end_char: int
    chunk_index: int


def split_text_into_chunks(
    text: str,
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Chunk]:
    """将文本按递归分隔 + 重叠策略切成 chunk。

    说明：
    - 先做换行规范化，避免不同平台换行导致切分不稳定。
    - 先递归按较大语义分隔符切分，再在极端长文本下退化为固定长度切片。
    - chunk 之间保留重叠，减少上下文被切断造成的语义丢失。
    """
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    # 先按语义边界递归拆分成“原始片段”。
    raw_chunks = _recursive_split(normalized, chunk_size, _DEFAULT_SEPARATORS)

    merged: list[Chunk] = []
    cursor = 0
    for idx, part in enumerate(raw_chunks):
        # 从当前游标向前回退 overlap 个字符，形成重叠区域。
        start = max(0, cursor - chunk_overlap) if idx > 0 else cursor
        end = min(len(normalized), start + len(part))
        merged.append(
            Chunk(
                text=normalized[start:end],
                start_char=start,
                end_char=end,
                chunk_index=idx,
            )
        )
        # 游标推进到当前 chunk 结尾，供下一个 chunk 计算重叠区间。
        cursor = end
    return merged


def _recursive_split(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    """递归按分隔符拆分文本，直到每段都不超过 chunk_size。

    核心思路：
    - 优先尝试使用更自然的分隔符（段落、句号等）。
    - 当前分隔符不可用时，继续尝试更细粒度分隔符。
    - 所有分隔符都无效时，退化为固定长度切片兜底。
    """
    if len(text) <= chunk_size:
        return [text]
    if not separators:
        # 兜底策略：直接按固定长度切片，保证算法一定有输出。
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    sep = separators[0]
    parts = text.split(sep)
    if len(parts) == 1:
        # 当前分隔符无法继续拆分，降级尝试下一层分隔符。
        return _recursive_split(text, chunk_size, separators[1:])

    chunks: list[str] = []
    current = ""
    for part in parts:
        # 尝试把当前段拼进候选 chunk，判断是否超过目标长度。
        candidate = part if not current else current + sep + part
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        # 当前候选过长，先把已积累的内容继续递归拆分。
        if current:
            chunks.extend(_recursive_split(current, chunk_size, separators[1:]))

        current = part
        if len(current) > chunk_size:
            # 单段仍然过长，继续向下拆分。
            chunks.extend(_recursive_split(current, chunk_size, separators[1:]))
            current = ""

    if current:
        chunks.extend(_recursive_split(current, chunk_size, separators[1:]))

    return [chunk for chunk in chunks if chunk.strip()]
