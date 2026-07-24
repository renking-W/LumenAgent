"""密码哈希与无状态 JWT 的签发、校验。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_KEY_BYTES = 32


def hash_password(password: str) -> str:
    """使用 scrypt 生成包含参数与盐值的密码哈希。"""
    salt = os.urandom(_SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_KEY_BYTES,
    )
    salt_text = base64.urlsafe_b64encode(salt).decode("ascii")
    hash_text = base64.urlsafe_b64encode(derived).decode("ascii")
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt_text}${hash_text}"


def verify_password(password: str, encoded_hash: str) -> bool:
    """校验密码；遇到不合法的历史哈希时按校验失败处理。"""
    try:
        algorithm, n, r, p, salt_text, hash_text = encoded_hash.split("$", 5)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(hash_text.encode("ascii"))
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(
    user_id: str,
    *,
    secret: str,
    expire_hours: int,
    refresh_before_hours: int,
) -> tuple[str, datetime, datetime]:
    """签发 JWT，并返回后台确定的过期时间和可刷新时间。"""
    if expire_hours <= 0 or not 0 < refresh_before_hours < expire_hours:
        raise ValueError("JWT 有效期必须大于刷新窗口，且二者都必须为正数")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=expire_hours)
    refresh_at = expires_at - timedelta(hours=refresh_before_hours)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": expires_at,
        "type": "access",
    }
    return jwt.encode(payload, secret, algorithm="HS256"), expires_at, refresh_at


def decode_access_token(token: str, *, secret: str) -> dict[str, Any]:
    """校验 JWT 签名、有效期及令牌类型。"""
    payload = jwt.decode(token, secret, algorithms=["HS256"])
    if payload.get("type") != "access" or not payload.get("sub"):
        raise jwt.InvalidTokenError("令牌类型或用户标识无效")
    return payload
