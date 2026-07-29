"""微信通道进程管理：随 FastAPI 启停 Node 服务，并代理本机控制请求。"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import shutil
from typing import Any

import httpx

from lumen_agent.application.service.chat.api_key_service import generate_api_key, hash_api_key
from lumen_agent.application.uitls.dir_guide import DirGuide
from lumen_agent.config import Settings, resolve_db_path
from lumen_agent.infrastructure.data_base.sqlite_api_key import SqliteApiKeyRepository

logger = logging.getLogger(__name__)
_CONTROL_PORT = 1676
_CONTROL_URL = f"http://127.0.0.1:{_CONTROL_PORT}"


class WeixinChannelUnavailableError(RuntimeError):
    """微信通道进程尚未就绪或无法连接。"""


class WeixinChannelRequestError(RuntimeError):
    """微信通道拒绝了管理请求。"""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code


class WeixinChannelManager:
    """管理唯一微信 Node 子进程，并在异常退出后自动重启。"""

    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._supervisor: asyncio.Task[None] | None = None
        self._closing = False
        self._control_token = ""
        self._lumen_api_key = ""

    async def start(self, settings: Settings) -> None:
        """准备内部凭据并启动常驻守护任务。"""
        if self._supervisor and not self._supervisor.done():
            return
        self._closing = False
        self._control_token = secrets.token_urlsafe(32)
        self._lumen_api_key = await self._ensure_internal_api_key(settings)
        self._supervisor = asyncio.create_task(
            self._supervise(), name="weixin-channel-supervisor"
        )

    async def stop(self) -> None:
        """停止守护任务和当前 Node 子进程。"""
        self._closing = True
        process = self._process
        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=8)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        self._process = None

        supervisor = self._supervisor
        self._supervisor = None
        if supervisor:
            supervisor.cancel()
            await asyncio.gather(supervisor, return_exceptions=True)

    async def status(self) -> dict[str, Any]:
        """返回绑定状态；进程未就绪时提供可展示的错误状态。"""
        try:
            return await self._request("GET", "/status")
        except WeixinChannelUnavailableError as exc:
            return {
                "phase": "error",
                "bound": False,
                "running": False,
                "last_error": str(exc),
            }

    async def begin_binding(self) -> dict[str, Any]:
        """生成二维码并开始后台轮询扫码状态。"""
        return await self._request("POST", "/binding", timeout=20)

    async def unbind(self) -> dict[str, Any]:
        """停止微信消息循环并删除本地微信凭据。"""
        return await self._request("DELETE", "/binding", timeout=20)

    async def _supervise(self) -> None:
        """子进程退出后退避重启，直到 FastAPI 关闭。"""
        retry_delay = 2
        while not self._closing:
            try:
                process = await self._spawn()
                self._process = process
                retry_delay = 2
                await process.wait()
                if not self._closing:
                    logger.error(
                        "微信通道进程异常退出 code=%s，%s 秒后重启",
                        process.returncode,
                        retry_delay,
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("微信通道进程启动失败，%s 秒后重试", retry_delay)
            finally:
                self._process = None

            if not self._closing:
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)

    async def _spawn(self) -> asyncio.subprocess.Process:
        """启动 tsx 控制服务，并将输出接入后端日志。"""
        node = shutil.which("node")
        if not node:
            raise WeixinChannelUnavailableError("未找到 Node.js 22 运行环境")

        channel_dir = DirGuide.project_root() / "weixinChannel"
        cli_path = channel_dir / "node_modules" / "tsx" / "dist" / "cli.mjs"
        entry_path = channel_dir / "src" / "main.ts"
        if not cli_path.is_file() or not entry_path.is_file():
            raise WeixinChannelUnavailableError(
                "微信通道依赖未安装，请在 weixinChannel 执行 npm install"
            )

        state_dir = channel_dir / "data"
        state_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(
            {
                "OPENCLAW_STATE_DIR": str(state_dir),
                "WEIXIN_CONTROL_TOKEN": self._control_token,
                "WEIXIN_CONTROL_PORT": str(_CONTROL_PORT),
                "LUMEN_API_KEY": self._lumen_api_key,
                # 与当前 FastAPI 实际监听端口保持一致，兼容本地 21675 和 Docker 1675。
                "LUMEN_BASE_URL": f"http://127.0.0.1:{os.getenv('PORT', '21675')}",
            }
        )

        process = await asyncio.create_subprocess_exec(
            node,
            str(cli_path),
            str(entry_path),
            cwd=str(channel_dir),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        asyncio.create_task(self._pipe_logs(process.stdout, logging.INFO))
        asyncio.create_task(self._pipe_logs(process.stderr, logging.WARNING))
        logger.info("微信通道进程已启动 pid=%s", process.pid)
        return process

    async def _request(
        self, method: str, path: str, *, timeout: float = 5
    ) -> dict[str, Any]:
        """携带进程级随机令牌访问仅监听回环地址的控制服务。"""
        process = self._process
        if not process or process.returncode is not None:
            raise WeixinChannelUnavailableError("微信通道进程尚未运行")

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method,
                    f"{_CONTROL_URL}{path}",
                    headers={"Authorization": f"Bearer {self._control_token}"},
                )
        except httpx.RequestError as exc:
            raise WeixinChannelUnavailableError("微信通道正在启动，请稍后重试") from exc

        if response.is_error:
            try:
                detail = str(response.json().get("detail", "微信通道请求失败"))
            except ValueError:
                detail = response.text or "微信通道请求失败"
            raise WeixinChannelRequestError(response.status_code, detail)
        return response.json()

    async def _ensure_internal_api_key(self, settings: Settings) -> str:
        """创建并复用微信通道专用 API Key，原文仅保存在权限受限文件。"""
        state_dir = DirGuide.project_root() / "weixinChannel" / "data"
        state_dir.mkdir(parents=True, exist_ok=True)
        key_path = state_dir / ".lumen_api_key"
        repo = SqliteApiKeyRepository(resolve_db_path(settings))

        if key_path.is_file():
            raw_key = key_path.read_text(encoding="utf-8").strip()
            key_hash = hash_api_key(raw_key)
            if key_hash and await repo.get_by_hash(key_hash):
                return raw_key

        raw_key, key_hash = generate_api_key()
        await repo.create(key_hash, name="Weixin Channel")
        key_path.write_text(raw_key, encoding="utf-8")
        try:
            key_path.chmod(0o600)
        except OSError:
            logger.warning("微信通道 API Key 文件权限设置失败：%s", key_path)
        return raw_key

    @staticmethod
    async def _pipe_logs(stream: asyncio.StreamReader | None, level: int) -> None:
        """逐行转发 Node 子进程日志。"""
        if stream is None:
            return
        while line := await stream.readline():
            logger.log(level, "[Weixin] %s", line.decode("utf-8", errors="replace").rstrip())


_manager = WeixinChannelManager()


def get_weixin_channel_manager() -> WeixinChannelManager:
    """返回进程内唯一微信通道管理器。"""
    return _manager
