"""微信通道管理员路由：查询状态、开始绑定和解除绑定。"""

from fastapi import APIRouter, HTTPException, status

from lumen_agent.api.schemas.weixin_dtos import WeixinChannelStatus
from lumen_agent.infrastructure.weixin_channel_manager import (
    WeixinChannelRequestError,
    WeixinChannelUnavailableError,
    get_weixin_channel_manager,
)

router = APIRouter(prefix="/v1/admin/weixin", tags=["admin-weixin"])


def _raise_channel_error(exc: Exception) -> None:
    """将内部控制服务错误转换为稳定的管理 API 状态码。"""
    if isinstance(exc, WeixinChannelRequestError):
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=str(exc),
    ) from exc


@router.get("/status", response_model=WeixinChannelStatus)
async def get_status() -> WeixinChannelStatus:
    """返回微信是否绑定以及消息循环是否运行。"""
    result = await get_weixin_channel_manager().status()
    return WeixinChannelStatus.model_validate(result)


@router.post(
    "/binding",
    response_model=WeixinChannelStatus,
    status_code=status.HTTP_202_ACCEPTED,
)
async def begin_binding() -> WeixinChannelStatus:
    """生成微信二维码，并在后台等待扫码确认。"""
    try:
        result = await get_weixin_channel_manager().begin_binding()
    except (WeixinChannelRequestError, WeixinChannelUnavailableError) as exc:
        _raise_channel_error(exc)
    return WeixinChannelStatus.model_validate(result)


@router.delete("/binding", response_model=WeixinChannelStatus)
async def unbind() -> WeixinChannelStatus:
    """停止消息循环并删除当前微信登录凭据。"""
    try:
        result = await get_weixin_channel_manager().unbind()
    except (WeixinChannelRequestError, WeixinChannelUnavailableError) as exc:
        _raise_channel_error(exc)
    return WeixinChannelStatus.model_validate(result)
