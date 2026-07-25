"""Agent 执行上下文中的当前用户身份。"""

from __future__ import annotations

from contextvars import ContextVar, Token

_current_user_id: ContextVar[str | None] = ContextVar(
    "chat_current_user_id",
    default=None,
)


def set_current_user_id(user_id: str | None) -> Token:
    """写入当前异步任务的用户 ID，并返回用于恢复上下文的 token。"""
    return _current_user_id.set(user_id)


def reset_current_user_id(token: Token) -> None:
    """恢复进入 Agent 执行前的用户身份上下文。"""
    try:
        _current_user_id.reset(token)
    except ValueError:
        # 异步生成器可能在不同 Context 中关闭，此时直接清空当前值。
        _current_user_id.set(None)


def get_current_user_id() -> str | None:
    """读取当前 Agent 执行对应的用户 ID。"""
    return _current_user_id.get()
