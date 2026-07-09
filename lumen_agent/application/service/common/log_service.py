"""日志读取服务：按文件倒序逐行读取、解析与过滤。"""

from __future__ import annotations

import logging
import re
from typing import Any

from lumen_agent.application.uitls.dir_guide import DirGuide

_logger = logging.getLogger(__name__)

# 日志行模式：asctime 可选毫秒 ",123"
_LOG_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d{3})?)"
    r"\s+-\s+(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+-\s+(.*)$",
)

_LOG_PATH = DirGuide.agent_log_path()


def _read_lines() -> list[str]:
    """读取 agent.log 全部行，文件不存在或读取出错时返回空列表。"""
    try:
        text = _LOG_PATH.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return text.splitlines()


def parse_log_line(line: str) -> dict[str, str] | None:
    """解析单行日志返回结构化字典，非日志行返回 None。"""
    m = _LOG_PATTERN.match(line.strip())
    if not m:
        return None
    ts = m.group(1)
    if "," in ts:
        ts = ts.split(",")[0]
    return {
        "timestamp": ts,
        "level": m.group(2),
        "message": m.group(3),
    }


def _matches_filter(
    entry: dict[str, str],
    level: str | None,
    keyword: str | None,
) -> bool:
    """判断一条结构化日志是否匹配过滤条件。"""
    if level and entry["level"] != level.upper():
        return False
    if keyword and keyword.lower() not in entry["message"].lower():
        return False
    return True


def read_logs(
    lines: int = 100,
    offset: int = 0,
    level: str | None = None,
    keyword: str | None = None,
) -> list[dict[str, str]]:
    """从 agent.log 倒序读取最多 ``lines`` 条满足条件的日志行。

    ``offset`` 跳过前 N 条匹配行，与 ``lines`` 配合实现滚动分页：
      - offset=0  lines=100  → 最新的 100 条
      - offset=100 lines=100 → 跳过最新的 100 条，取接下来的 100 条

    返回结果已按时间倒序排列（最新在前）。
    """
    all_lines = _read_lines()
    result: list[dict[str, str]] = []
    skip = offset

    for line in reversed(all_lines):
        if not line.strip():
            continue
        entry = parse_log_line(line)
        if entry is None:
            continue
        if not _matches_filter(entry, level, keyword):
            continue
        if skip > 0:
            skip -= 1
            continue
        result.append(entry)
        if len(result) >= lines:
            break

    return result


def count_logs(
    level: str | None = None,
    keyword: str | None = None,
) -> int:
    """统计 agent.log 中满足过滤条件的日志总行数。"""
    all_lines = _read_lines()
    total = 0

    for line in all_lines:
        entry = parse_log_line(line)
        if entry is None:
            continue
        if not _matches_filter(entry, level, keyword):
            continue
        total += 1

    return total

def log_directory() -> str:
    """返回日志目录。"""
    return str(_LOG_PATH.parent)