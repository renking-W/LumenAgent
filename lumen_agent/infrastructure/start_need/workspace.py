"""工作区初始化：目录创建与模板文件拷贝。"""

from __future__ import annotations

import logging
import shutil

from lumen_agent.application.uitls.dir_guide import DirGuide

logger = logging.getLogger(__name__)

# ── 模板文档目录 ─────────────────────────────────────────────
_DOCS_DIR = DirGuide.docs_dir()
# ── 需要拷贝到工作区的文件 ────────────────────────────────────
_WORKSPACE_SEED_FILES = ["ME.md", "MEMORY.md", "RULE.md", "USER.md"]


def _ensure_runtime_dirs() -> None:
    """创建项目启动依赖的运行时目录。"""
    for directory in (
        DirGuide.data_dir(),
        DirGuide.chroma_dir(),
        DirGuide.agent_log_path().parent,
        DirGuide.machine_log_dir(),
        DirGuide.tmp_dir(),
    ):
        directory.mkdir(parents=True, exist_ok=True)


def init_workspace() -> None:
    """初始化 Agent 工作区和项目运行所需目录。"""
    _ensure_runtime_dirs()

    workspace = DirGuide.workspace_dir()
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
