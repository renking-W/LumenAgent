"""存量 MCP Server description 批量回填。

对 DB 中所有 HTTP / stdio MCP Server 调用 LLM 生成 description，
enabled 的 server 会先 sync 工具索引，再生成描述并二次 sync search_doc。

用法（在项目根目录执行）::

    python scripts/backfill_mcp_descriptions.py
    python scripts/backfill_mcp_descriptions.py --only-empty
    python scripts/backfill_mcp_descriptions.py --force
    python scripts/backfill_mcp_descriptions.py --dry-run

依赖：`.env` 中已配置 LLM（LLM_API_KEY 等）；enabled 的 MCP 需可连接。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

# 允许直接 ``python scripts/backfill_mcp_descriptions.py`` 运行
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lumen_agent.application.service.mcp.mcp_description_service import (
    refresh_server_description_after_sync,
)
from lumen_agent.application.service.mcp.mcp_tool_sync_service import McpToolSyncService
from lumen_agent.config import get_settings, resolve_db_path
from lumen_agent.infrastructure.data_base.sqlite_mcp import SqliteMCPServerRepository
from lumen_agent.infrastructure.data_base.sqlite_mcp_stdio import SqliteMCPStdioServerRepository
from lumen_agent.model_adapters import get_model_adapter
from lumen_agent.model_adapters.client import get_mcp_manager

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量生成存量 MCP Server 的 description")
    parser.add_argument(
        "--only-empty",
        action="store_true",
        help="仅处理 description 为空的 server（默认：处理全部）",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="即使已有 description 也强制重生成（与 --only-empty 互斥，--only-empty 优先）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只列出将要处理的 server，不调用 LLM、不写库",
    )
    parser.add_argument(
        "--kind",
        choices=("http", "stdio", "all"),
        default="all",
        help="限定 server 类型（默认 all）",
    )
    return parser.parse_args()


def _should_process(server: dict[str, Any], *, only_empty: bool, force: bool) -> bool:
    """根据 CLI 参数判断是否需要处理该 server。"""
    desc = (server.get("description") or "").strip()
    if only_empty:
        return not desc
    if force:
        return True
    # 默认：全部处理（存量迁移场景）
    return True


async def _connect_enabled_mcp(
    http_repo: SqliteMCPServerRepository,
    stdio_repo: SqliteMCPStdioServerRepository,
) -> None:
    """连接所有已启用的 MCP，便于 sync 时复用 manager 连接。"""
    mgr = get_mcp_manager()
    enabled_http = await http_repo.list_enabled()
    enabled_stdio = await stdio_repo.list_enabled()
    await mgr.start_all(enabled_http)
    await mgr.start_all_stdio(enabled_stdio)
    logger.info(
        "MCP 管理器已连接 %d 个 server（http=%d stdio=%d）",
        len(mgr.list_connection_ids()),
        len(enabled_http),
        len(enabled_stdio),
    )


async def _process_one(
    *,
    kind: str,
    server: dict[str, Any],
    settings,
    llm,
    sync_service: McpToolSyncService,
    dry_run: bool,
) -> str | None:
    """处理单个 server：可选 sync → 生成 description。"""
    sid = server["id"]
    name = server["name"]
    enabled = bool(server.get("enabled"))

    if dry_run:
        desc_preview = (server.get("description") or "").strip()
        print(
            f"  [dry-run] {kind}/{name} ({sid}) "
            f"enabled={enabled} tools_sync=待执行 desc_len={len(desc_preview)}"
        )
        return None

    tool_count = 0
    if enabled:
        try:
            tool_count = await sync_service.sync_server(kind, sid)
            logger.info("%s/%s 工具索引已同步：%d 个", kind, name, tool_count)
        except Exception:
            logger.exception("%s/%s 工具 sync 失败，将基于已有索引或空工具列表生成", kind, name)

    description = await refresh_server_description_after_sync(
        llm,
        settings,
        server_kind=kind,
        server_id=sid,
        server_name=name,
        user_hint=None,  # 存量回填不传 user_hint，避免旧文本自我强化
        resync=True,
    )
    print(f"  OK {kind}/{name} ({sid}) → {len(description)} 字")
    return description


async def async_main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    settings = get_settings()
    if not settings.get("LLM_API_KEY", "").strip():
        logger.error("LLM_API_KEY 未配置，无法生成 description")
        return 1

    db_path = resolve_db_path(settings)
    http_repo = SqliteMCPServerRepository(db_path)
    stdio_repo = SqliteMCPStdioServerRepository(db_path)

    targets: list[tuple[str, dict[str, Any]]] = []
    if args.kind in ("http", "all"):
        for svr in await http_repo.list_all():
            if _should_process(svr, only_empty=args.only_empty, force=args.force):
                targets.append(("http", svr))
    if args.kind in ("stdio", "all"):
        for svr in await stdio_repo.list_all():
            if _should_process(svr, only_empty=args.only_empty, force=args.force):
                targets.append(("stdio", svr))

    if not targets:
        print("没有需要处理的 MCP Server。")
        return 0

    print(f"共 {len(targets)} 个 MCP Server 待处理"
          + ("（dry-run）" if args.dry_run else "") + "：")
    for kind, svr in targets:
        print(f"  - [{kind}] {svr['name']} ({svr['id']})")

    if args.dry_run:
        return 0

    llm = get_model_adapter(settings)
    sync_service = McpToolSyncService(settings)

    try:
        await _connect_enabled_mcp(http_repo, stdio_repo)
    except Exception:
        logger.exception("MCP 管理器连接部分失败，enabled server 将尝试临时连接 sync")

    ok, fail = 0, 0
    for kind, svr in targets:
        try:
            await _process_one(
                kind=kind,
                server=svr,
                settings=settings,
                llm=llm,
                sync_service=sync_service,
                dry_run=False,
            )
            ok += 1
        except Exception:
            logger.exception("处理失败：%s/%s", kind, svr.get("name"))
            fail += 1

    print(f"\n完成：成功 {ok}，失败 {fail}，合计 {len(targets)}")

    try:
        await get_mcp_manager().close_all()
    except Exception:
        logger.exception("MCP 管理器关闭时异常")

    return 0 if fail == 0 else 2


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
