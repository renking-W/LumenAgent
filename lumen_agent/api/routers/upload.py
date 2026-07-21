"""文件上传路由：POST /v1/upload 保存文件；GET /v1/files/{filename} 取回文件。"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from lumen_agent.api.dependency import verify_api_key
from lumen_agent.api.schemas.upload_dtos import UploadResponse
from lumen_agent.application.uitls.dir_guide import DirGuide

router = APIRouter(prefix="/v1", tags=["upload"])

_MAX_UPLOAD_BYTES = 100 * 1024 * 1024
_UPLOAD_CHUNK_BYTES = 1024 * 1024


def _safe_filename(original_filename: str) -> str:
    """保留可识别的原文件名，并移除路径与 Windows 非法字符。"""
    basename = original_filename.replace(chr(92), "/").rsplit("/", 1)[-1]
    path = Path(basename or "upload.bin")
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", path.stem).strip(" .")
    suffix = re.sub(r"[^A-Za-z0-9.]", "", path.suffix)[:20]
    safe_stem = (stem or "upload")[:100]
    return f"{safe_stem}_{uuid.uuid4().hex[:8]}{suffix}"


@router.post(
    "/upload",
    response_model=UploadResponse,
    dependencies=[Depends(verify_api_key)],
)
async def upload_file(file: UploadFile) -> UploadResponse:
    """上传任意类型文件到 work_space/tmp/，单文件最大 100 MB。"""
    content_type = file.content_type or "application/octet-stream"

    tmp_dir: Path = DirGuide.tmp_dir()
    tmp_dir.mkdir(parents=True, exist_ok=True)

    filename = _safe_filename(file.filename or "")
    dest = tmp_dir / filename

    size = 0
    try:
        with dest.open("wb") as output:
            while chunk := await file.read(_UPLOAD_CHUNK_BYTES):
                size += len(chunk)
                if size > _MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="文件大小不能超过 100 MB",
                    )
                output.write(chunk)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    return UploadResponse(
        filename=filename,
        url=f"/v1/files/{filename}",
        path=str(dest.resolve()),
        content_type=content_type,
        size=size,
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
