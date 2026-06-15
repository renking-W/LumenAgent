"""Flask 静态文件服务 + /v1/* API 代理（SSE 流式转发）。"""

from __future__ import annotations

import logging
import os

import httpx
from flask import Flask, Response, request, send_from_directory, stream_with_context

from lumen_agent.config import _PROJECT_ROOT

logger = logging.getLogger(__name__)

_FRONTEND_PORT = 1675
_PROXY_TARGET = "http://127.0.0.1:21675"


def run_frontend() -> None:
    """启动 Flask 服务：serve 前端静态文件，/v1/* 代理到 FastAPI。"""
    # static_folder 使用绝对路径，不受模块位置影响
    static_dir = str(_PROJECT_ROOT / "webChannel" / "dist")
    front = Flask(__name__, static_folder=static_dir, static_url_path="")
    proxy_client = httpx.Client(base_url=_PROXY_TARGET, timeout=None)

    # ── 代理 /v1/* 到 FastAPI ──────────────────────────
    def _forward_headers():
        return {
            k: v for k, v in request.headers
            if k.lower() not in ("host", "content-length", "transfer-encoding")
        }

    # SSE 流式端点：用 httpx stream=True，通过 Flask Response 流式转发
    @front.route("/v1/chat/stream", methods=["POST", "OPTIONS"])
    def proxy_chat_stream():
        try:
            req = proxy_client.build_request(
                "POST", "/v1/chat/stream",
                params=request.args,
                content=request.get_data(),
                headers=_forward_headers(),
            )
            upstream = proxy_client.send(req, stream=True)

            def generate():
                try:
                    for chunk in upstream.iter_bytes():
                        yield chunk
                finally:
                    upstream.close()

            # 移除可能导致冲突的头部
            hop_by_hop = {"transfer-encoding", "content-length", "connection"}
            headers = {k: v for k, v in upstream.headers.items() if k.lower() not in hop_by_hop}
            return Response(
                stream_with_context(generate()),
                status=upstream.status_code,
                headers=headers,
            )
        except httpx.RequestError as e:
            return {"error": f"代理请求失败: {e}"}, 502

    # 通用代理（非 SSE 全量读取）
    @front.route("/v1/<path:subpath>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    def proxy_api(subpath):
        # /v1/chat/stream 已有专用路由，跳过
        if subpath == "chat/stream":
            return "Not Found", 404
        try:
            resp = proxy_client.request(
                method=request.method,
                url=f"/v1/{subpath}",
                params=request.args,
                content=request.get_data(),
                headers=_forward_headers(),
            )
            return resp.content, resp.status_code, dict(resp.headers)
        except httpx.RequestError as e:
            return {"error": f"代理请求失败: {e}"}, 502

    # ── 首页 ──────────────────────────────────────────
    @front.route("/")
    def index():
        return send_from_directory(front.static_folder, "index.html")

    # ── SPA 兜底：404 时返回 index.html ──────────────
    @front.errorhandler(404)
    def not_found(e):
        file_path = request.path.lstrip("/")
        full = os.path.join(front.static_folder, file_path)
        if file_path and os.path.isfile(full):
            return send_from_directory(front.static_folder, file_path)
        return send_from_directory(front.static_folder, "index.html")

    front.run(host="0.0.0.0", port=_FRONTEND_PORT)
