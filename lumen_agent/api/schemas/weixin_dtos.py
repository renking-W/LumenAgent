"""微信通道 DTO：绑定状态和二维码信息。"""

from typing import Literal

from pydantic import BaseModel


class WeixinChannelStatus(BaseModel):
    """管理员页面使用的微信通道公开状态。"""

    phase: Literal[
        "unbound",
        "waiting_scan",
        "scanned",
        "bound",
        "running",
        "error",
    ]
    bound: bool
    running: bool
    qrcode_url: str | None = None
    account_id: str | None = None
    last_error: str | None = None
