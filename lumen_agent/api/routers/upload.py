"""文件上传路由：POST /v1/upload 保存文件；GET /v1/files/{filename} 取回文件。"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from lumen_agent.api.dependency import verify_api_key
from lumen_agent.api.schemas.upload_dtos import UploadResponse
from lumen_agent.application.uitls.dir_guide import DirGuide

router = APIRouter(prefix="/v1", tags=["upload"])

_ALLOWED_IMAGE_MIME_PREFIXES = ("image/jpeg", "image/png", "image/gif", "image/webp", "image/")

_EXT_MAP: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def _resolve_ext(content_type: str, original_filename: str) -> str:
    """从 MIME 或原始文件名推断扩展名。"""
    if content_type in _EXT_MAP:
        return _EXT_MAP[content_type]
    suffix = Path(original_filename).suffix
    return suffix if suffix else ".bin"


@router.post(
    "/upload",
    response_model=UploadResponse,
    dependencies=[Depends(verify_api_key)],
)
async def upload_file(file: UploadFile) -> UploadResponse:
    """上传文件（当前仅支持图片）并保存到 work_space/tmp/。

    返回本地可访问的文件 URL，前端将其放入 ChatRequest.image_urls
    交给 agent 流式入口时注入给 LLM。
    """
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"当前仅支持图片上传，收到的类型为：{content_type}",
        )

    tmp_dir: Path = DirGuide.tmp_dir()
    tmp_dir.mkdir(parents=True, exist_ok=True)

    ext = _resolve_ext(content_type, file.filename or "")
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = tmp_dir / filename

    data = await file.read()
    dest.write_bytes(data)

    return UploadResponse(
        filename=filename,
        url=f"/v1/files/{filename}",
        content_type=content_type,
        size=len(data),
    )


@router.get("/files/{filename}")
async def get_file(filename: str) -> FileResponse:
    """取回已上传的文件（无需认证，便于前端直接预览）。

    做基础路径穿越防护：文件名不得含路径分隔符或 '..'。
    """
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法文件名")

    tmp_dir: Path = DirGuide.tmp_dir()
    file_path = tmp_dir / filename

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    return FileResponse(path=str(file_path), filename=filename)
