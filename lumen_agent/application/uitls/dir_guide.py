"""项目路径统一引导 —— 消除散落各处的 ``Path(__file__).resolve().parent...``。

所有需要引用项目目录的模块均应使用 ``DirGuide`` 而非自己计算路径。
"""

from __future__ import annotations

from pathlib import Path


class DirGuide:
    """LumenAgent 目录引导 —— 单锚点计算，类方法访问。"""

    # ── 单锚点 ─────────────────────────────────────────────────────
    # 基于本文件位置计算：
    #   dir_guide.py → application/uitls/ → application/ → lumen_agent/
    _PACKAGE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    _PROJECT_ROOT: Path = _PACKAGE_DIR.parent

    # ── 包级路径（lumen_agent/ 下） ────────────────────────────────

    @classmethod
    def package_dir(cls) -> Path:
        """返回 ``lumen_agent/`` 包根目录的绝对路径。"""
        return cls._PACKAGE_DIR

    @classmethod
    def project_root(cls) -> Path:
        """返回项目根目录（``package_dir()`` 的父目录）。"""
        return cls._PROJECT_ROOT

    @classmethod
    def data_dir(cls) -> Path:
        """返回 ``lumen_agent/data/``。"""
        return cls._PACKAGE_DIR / "data"

    @classmethod
    def chroma_dir(cls) -> Path:
        """返回 ``lumen_agent/data/chroma/``。"""
        return cls._PACKAGE_DIR / "data" / "chroma"

    @classmethod
    def knowledge_db_path(cls) -> Path:
        """返回 ``lumen_agent/data/knowledge.db``。"""
        return cls._PACKAGE_DIR / "data" / "knowledge.db"

    @classmethod
    def knowledge_index_path(cls) -> Path:
        """返回 ``lumen_agent/data/chroma/knowledge_index.json``。"""
        return cls._PACKAGE_DIR / "data" / "chroma" / "knowledge_index.json"

    @classmethod
    def config_json_path(cls) -> Path:
        """返回 ``lumen_agent/config.json``。"""
        return cls._PACKAGE_DIR / "config.json"

    @classmethod
    def env_path(cls) -> Path:
        """返回 ``lumen_agent/.env``。"""
        return cls._PACKAGE_DIR / ".env"

    @classmethod
    def docs_dir(cls) -> Path:
        """返回 ``lumen_agent/agent/prompts/docs/``。"""
        return cls._PACKAGE_DIR / "agent" / "prompts" / "docs"

    @classmethod
    def title_prompt_path(cls) -> Path:
        """返回 ``docs/title.md``。"""
        return cls.docs_dir() / "title.md"

    @classmethod
    def summary_prompt_path(cls) -> Path:
        """返回 ``docs/summary.md``。"""
        return cls.docs_dir() / "summary.md"

    @classmethod
    def memory_refine_prompt_path(cls) -> Path:
        """返回 ``docs/memory_refine.md``。"""
        return cls.docs_dir() / "memory_refine.md"

    @classmethod
    def mcp_server_description_prompt_path(cls) -> Path:
        """返回 ``docs/mcp_server_description.md``。"""
        return cls.docs_dir() / "mcp_server_description.md"

    @classmethod
    def agent_log_path(cls) -> Path:
        """返回 ``lumen_agent/log/agent.log``。"""
        return cls._PACKAGE_DIR / "log" / "agent.log"

    @classmethod
    def machine_log_dir(cls) -> Path:
        """返回 ``lumen_agent/log/machine_log/``。"""
        return cls._PACKAGE_DIR / "log" / "machine_log"

    # ── Workspace 路径（<项目根>/work_space/ 下） ─────────────────

    @classmethod
    def workspace_dir(cls) -> Path:
        """返回 ``<项目根>/work_space/``。"""
        return cls._PROJECT_ROOT / "work_space"

    @classmethod
    def memory_dir(cls) -> Path:
        """返回 ``<项目根>/work_space/memory/``。"""
        return cls.workspace_dir() / "memory"

    @classmethod
    def skills_dir(cls) -> Path:
        """返回 ``<项目根>/work_space/skills/``。"""
        return cls.workspace_dir() / "skills"

    @classmethod
    def tmp_dir(cls) -> Path:
        """返回 ``<项目根>/work_space/tmp/``（临时上传文件）。"""
        return cls.workspace_dir() / "tmp"

    # ── 前端路径 ───────────────────────────────────────────────────

    @classmethod
    def web_channel_dist_dir(cls) -> Path:
        """返回 ``<项目根>/webChannel/dist/``。"""
        return cls._PROJECT_ROOT / "webChannel" / "dist"
