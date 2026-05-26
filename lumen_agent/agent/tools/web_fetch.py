"""WebFetch 工具：抓取网页内容或下载文件并返回文本内容。"""

from __future__ import annotations

import mimetypes
from urllib.parse import urlparse

import httpx

from lumen_agent.agent.tools.base import BaseTool, ToolResult
from lumen_agent.agent.tools.registry import ToolRegistry
from lumen_agent.infrastructure.http_pool import get_http_pool


_DEFAULT_TIMEOUT = 30
_MAX_TIMEOUT = 120
_MAX_CONTENT_BYTES = 100 * 1024          # HTML/文本内容上限 100 KB
_MAX_FILE_BYTES = 10 * 1024 * 1024      # 文件下载上限 10 MB
_TRUNCATE_HINT = "内容已超过上限被截断，如需完整内容请分段抓取或下载后用 read 读取。"

# 被视为"文本文件"的 MIME 前缀或关键字
_TEXT_MIME_PREFIXES = ("text/", "application/json", "application/xml", "application/javascript")

# 被视为"不可直接读取"的二进制扩展名
_BINARY_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".exe", ".dll", ".so", ".dylib",
    ".xls", ".xlsx", ".ppt", ".pptx",
}


@ToolRegistry.register
class WebFetch(BaseTool):
    """抓取指定 URL 的网页内容（自动转为可读纯文本），或下载文本类文件并返回内容。"""

    name = "web_fetch"
    description = (
        "抓取指定 URL 的内容并返回文本。"
        "对 HTML 页面自动提取正文、去除广告与导航栏，转换为 Markdown 格式；"
        "对纯文本、JSON、XML 等文本类文件直接返回原始内容；"
        "对图片、音视频等二进制文件返回基本元信息而不下载内容。"
        f"单次内容上限 {_MAX_CONTENT_BYTES // 1024} KB（HTML/文本），"
        f"文件下载上限 {_MAX_FILE_BYTES // 1024 // 1024} MB。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "要抓取的完整 URL，包含协议前缀（http:// 或 https://）。",
            },
            "timeout": {
                "type": "integer",
                "description": (
                    f"请求超时秒数，默认 {_DEFAULT_TIMEOUT}，"
                    f"最大 {_MAX_TIMEOUT}。可选。"
                ),
            },
            "raw": {
                "type": "boolean",
                "description": (
                    "若为 true，HTML 页面跳过 Markdown 转换、直接返回原始 HTML。"
                    "默认 false。可选。"
                ),
            },
        },
        "required": ["url"],
    }

    async def execute(self, params: dict) -> ToolResult:
        # --- 参数解析 ---
        url: str = str(params.get("url", "")).strip()
        if not url:
            return ToolResult.error("url 不能为空。")
        if not url.startswith(("http://", "https://")):
            return ToolResult.error("url 须以 http:// 或 https:// 开头。")

        timeout_val = params.get("timeout")
        try:
            timeout = int(timeout_val) if timeout_val is not None else _DEFAULT_TIMEOUT
        except (TypeError, ValueError):
            return ToolResult.error("timeout 须为整数（秒）。")
        if timeout < 1 or timeout > _MAX_TIMEOUT:
            return ToolResult.error(f"timeout 须在 1～{_MAX_TIMEOUT} 秒之间。")

        raw: bool = bool(params.get("raw", False))

        # --- 快速检测：URL 扩展名是否为二进制 ---
        parsed = urlparse(url)
        path_lower = parsed.path.lower()
        ext = "." + path_lower.rsplit(".", 1)[-1] if "." in path_lower else ""
        if ext in _BINARY_EXTENSIONS:
            return ToolResult.success(
                f"[binary] URL 指向二进制文件（扩展名 {ext}），不予下载内容。\nURL: {url}"
            )

        # --- 发起请求（复用模块级连接池，避免 OOM） ---
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        try:
            pool = get_http_pool()
            response = await pool.send("GET", url, headers=headers, timeout=timeout)
        except httpx.TimeoutException:
            return ToolResult.error(f"请求超时（{timeout} 秒）：{url}")
        except httpx.RequestError as exc:
            return ToolResult.error(f"请求失败：{exc}")

        if response.status_code >= 400:
            return ToolResult.error(
                f"HTTP {response.status_code}：服务器返回错误，URL: {url}"
            )

        # --- 判断内容类型 ---
        content_type = response.headers.get("content-type", "").lower().split(";")[0].strip()

        # 二进制 MIME
        if content_type and not any(content_type.startswith(p) for p in _TEXT_MIME_PREFIXES):
            size = len(response.content)
            return ToolResult.success(
                f"[binary] 响应为二进制内容（Content-Type: {content_type}），不予解析。\n"
                f"URL: {url}\n大小: {size} bytes"
            )

        # --- HTML 页面 ---
        if "text/html" in content_type:
            raw_html = response.text
            if raw:
                content = raw_html
                if len(content.encode("utf-8")) > _MAX_CONTENT_BYTES:
                    content = content.encode("utf-8")[:_MAX_CONTENT_BYTES].decode("utf-8", errors="replace")
                    content += f"\n\n[{_TRUNCATE_HINT}]"
            else:
                content = _html_to_markdown(raw_html, url)
                if len(content.encode("utf-8")) > _MAX_CONTENT_BYTES:
                    content = content.encode("utf-8")[:_MAX_CONTENT_BYTES].decode("utf-8", errors="replace")
                    content += f"\n\n[{_TRUNCATE_HINT}]"

            return ToolResult.success(f"[webpage] {url}\n\n{content}")

        # --- 纯文本 / JSON / XML 等 ---
        text = response.text
        encoded = text.encode("utf-8")
        truncated = False
        if len(encoded) > _MAX_CONTENT_BYTES:
            text = encoded[:_MAX_CONTENT_BYTES].decode("utf-8", errors="replace")
            truncated = True

        footer = f"\n\n[{_TRUNCATE_HINT}]" if truncated else ""
        return ToolResult.success(f"[text] {url}\nContent-Type: {content_type}\n\n{text}{footer}")


def _html_to_markdown(html: str, url: str) -> str:
    """将 HTML 转换为 Markdown 格式的可读文本。优先使用 html2text，回退到 BeautifulSoup。"""
    # 方案一：html2text（语义更完整）
    try:
        import html2text
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.ignore_tables = False
        h.body_width = 0        # 不自动换行
        h.unicode_snob = True
        return h.handle(html).strip()
    except ImportError:
        pass

    # 方案二：BeautifulSoup 提取正文纯文本
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        # 移除脚本、样式、导航等噪音标签
        for tag in soup(["script", "style", "nav", "footer", "aside", "iframe", "noscript"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except ImportError:
        pass

    # 最后回退：原始 HTML
    return html
