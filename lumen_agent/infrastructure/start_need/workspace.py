"""工作区初始化：目录创建与模板文件拷贝。"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from lumen_agent.config import _PROJECT_ROOT

logger = logging.getLogger(__name__)

# ── 模板文档目录 ─────────────────────────────────────────────
_DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "agent" / "prompts" / "docs"
# ── 需要拷贝到工作区的文件 ────────────────────────────────────
_WORKSPACE_SEED_FILES = ["ME.md", "MEMORY.md", "RULE.md", "USER.md"]


def init_workspace() -> None:
    """初始化工作区：work_space 不存在时自动创建目录结构并拷贝模板文件。"""
    workspace = _PROJECT_ROOT / "work_space"
    if workspace.exists():
        return

    logging.info("工作区不存在，触发初始化：%s", workspace)

    # 创建目录结构
    (workspace / "memory").mkdir(parents=True, exist_ok=True)
    (workspace / "skills").mkdir(parents=True, exist_ok=True)
    (workspace / "konwledge").mkdir(parents=True, exist_ok=True)

    # 拷贝模板文件
    for filename in _WORKSPACE_SEED_FILES:
        src = _DOCS_DIR / filename
        if src.exists():
            shutil.copy2(src, workspace / filename)
            logging.info("  已拷贝：%s → work_space/%s", filename, filename)
        else:
            logging.warning("  模板文件不存在，跳过：%s", src)

    logging.info("工作区初始化完成：")
