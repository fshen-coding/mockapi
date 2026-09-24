# -*- coding: utf-8 -*-
"""Admin-managed image templates used by DOWSURE CNY company mock steps."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from web.models.responses import ApiResponse
from web.routes.auth_guard import require_admin, require_valid_username
from web.services.audit_store import audit_store

router = APIRouter(prefix="/api/company-image-templates", tags=["Company Image Templates"])

ImageType = Literal["business_license", "director_id_front", "director_id_back"]
MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}
BUILTIN_IMAGE_FILES = {
    "business_license": "business_license.png",
    "director_id_front": "director_id_front.png",
    "director_id_back": "director_id_back.png",
}
BUILTIN_IMAGE_DIR = Path(__file__).resolve().parents[1] / "assets" / "dowsure_cny"


async def _read_image(file: UploadFile) -> tuple[str, str, bytes]:
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 PNG、JPEG、WEBP 图片")
    content = await file.read(MAX_IMAGE_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="图片文件不能为空")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="图片大小不能超过 10MB")
    filename = Path(file.filename or "image.png").name
    return filename, content_type, content


@router.get("", response_model=ApiResponse)
async def list_company_image_templates(username: str | None = None):
    require_valid_username(username)
    rows = await asyncio.to_thread(audit_store.list_company_image_templates)
    return ApiResponse(success=True, message=f"{len(rows)} image templates", data=rows)


@router.post("", response_model=ApiResponse)
async def create_company_image_template(
    username: str = Form(...),
    name: str = Form(...),
    image_type: ImageType = Form(...),
    file: UploadFile = File(...),
):
    caller = require_admin(username)
    normalized_name = name.strip()
    if not normalized_name:
        raise HTTPException(status_code=400, detail="图片名称不能为空")
    filename, content_type, content = await _read_image(file)
    try:
        row = await asyncio.to_thread(
            audit_store.create_company_image_template,
            normalized_name,
            image_type,
            filename,
            content_type,
            content,
            caller,
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            raise HTTPException(status_code=400, detail="同类型下已存在相同名称") from exc
        raise
    return ApiResponse(success=True, message="图片模板已创建", data=row)


@router.put("/{template_id}", response_model=ApiResponse)
async def update_company_image_template(
    template_id: int,
    username: str = Form(...),
    name: str = Form(...),
    image_type: ImageType = Form(...),
    file: UploadFile | None = File(default=None),
):
    caller = require_admin(username)
    normalized_name = name.strip()
    if not normalized_name:
        raise HTTPException(status_code=400, detail="图片名称不能为空")
    filename = None
    content_type = None
    content = None
    if file is not None:
        filename, content_type, content = await _read_image(file)
    try:
        row = await asyncio.to_thread(
            audit_store.update_company_image_template,
            template_id,
            normalized_name,
            image_type,
            caller,
            filename,
            content_type,
            content,
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            raise HTTPException(status_code=400, detail="同类型下已存在相同名称") from exc
        raise
    if not row:
        raise HTTPException(status_code=404, detail="图片模板不存在")
    return ApiResponse(success=True, message="图片模板已更新", data=row)


@router.delete("/{template_id}", response_model=ApiResponse)
async def delete_company_image_template(template_id: int, username: str):
    require_admin(username)
    ok = await asyncio.to_thread(audit_store.delete_company_image_template, template_id)
    if not ok:
        raise HTTPException(status_code=404, detail="图片模板不存在")
    return ApiResponse(success=True, message="图片模板已删除", data={"id": str(template_id)})


@router.get("/{template_id}/content")
async def get_company_image_template_content(template_id: int, username: str | None = None):
    require_valid_username(username)
    row = await asyncio.to_thread(audit_store.get_company_image_template, template_id)
    if not row:
        raise HTTPException(status_code=404, detail="图片模板不存在")
    return Response(
        content=row["file_data"],
        media_type=row["content_type"],
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(row['filename'])}"},
    )


@router.get("/builtin/{image_type}/content")
async def get_builtin_company_image_content(
    image_type: ImageType,
    username: str | None = None,
):
    require_valid_username(username)
    filename = BUILTIN_IMAGE_FILES[image_type]
    file_path = BUILTIN_IMAGE_DIR / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="内置图片不存在")
    return Response(
        content=file_path.read_bytes(),
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
