"""API Key 管理服务：密钥生成、哈希、校验。"""

from __future__ import annotations

import hashlib
import secrets
from typing import Tuple


# ── 格式常量 ───────────────────────────────────────────────────────
_KEY_PREFIX = "lumen_"


def generate_api_key() -> Tuple[str, str]:
    """生成一组 (原始Key, SHA-256摘要)。

    原始 Key 格式 ``lumen_`` + 43 位 base64 URL-safe 字符，共 49 字符、256 位熵。
    生产者调用后应将 ``key_hash`` 持久化、将 ``raw_key`` 一次性返回给用户。
    """
    raw = _KEY_PREFIX + secrets.token_urlsafe(32)
    key_hash = _hash_raw(raw)
    return raw, key_hash


def hash_api_key(raw_key: str) -> str | None:
    """对传入的原始 Key 计算 SHA-256 摘要。

    若格式不合法（无 ``lumen_`` 前缀或长度不符）则返回 None。
    合法格式则返回 64 字符 hex 摘要。
    """
    if not raw_key.startswith(_KEY_PREFIX):
        return None
    # 最小长度 = 前缀 + 至少 16 字符
    if len(raw_key) < len(_KEY_PREFIX) + 16:
        return None
    return _hash_raw(raw_key)


def _hash_raw(raw: str) -> str:
    """SHA-256 摘要（内部使用）。"""
    return hashlib.sha256(raw.encode()).hexdigest()


def is_valid_format(raw_key: str) -> bool:
    """检查 Key 格式是否合法（前缀 + 足够长度）。"""
    return hash_api_key(raw_key) is not None
