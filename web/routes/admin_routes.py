# -*- coding: utf-8 -*-
"""Admin-only user management routes."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from web.models.requests import AdminUserDeleteRequest, AdminUserReviewRequest, AdminUserUpdateRequest
from web.models.responses import ApiResponse
from web.routes.auth_guard import require_admin
from web.services.audit_store import ADMIN_USERNAME, audit_store
from web.services.notify_manager import notify_manager

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["管理员"])


@router.get("/users", response_model=ApiResponse)
async def list_users(username: str | None = None):
    """Admin: list all registered accounts."""
    require_admin(username)
    rows = await asyncio.to_thread(audit_store.list_users)
    return ApiResponse(success=True, message=f"{len(rows)} 个账号", data=rows)


@router.put("/users/{target_username}", response_model=ApiResponse)
async def update_user(target_username: str, req: AdminUserUpdateRequest):
    """Admin: rename account, reset password, and/or edit notes."""
    require_admin(req.admin_username)
    if target_username == ADMIN_USERNAME and req.new_username and req.new_username != ADMIN_USERNAME:
        raise HTTPException(status_code=400, detail="不能修改内置管理员账号名")
    payload: dict = {}
    if req.new_username is not None:
        payload["new_username"] = req.new_username
    if req.new_password is not None:
        payload["new_password"] = req.new_password
    if req.notes is not None:
        payload["notes"] = req.notes
    try:
        row = await asyncio.to_thread(audit_store.update_user, target_username, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail=f"账号「{target_username}」不存在")
    return ApiResponse(success=True, message="账号已更新", data=row)


@router.delete("/users/{target_username}", response_model=ApiResponse)
async def delete_user(target_username: str, req: AdminUserDeleteRequest):
    """Admin: permanently delete a user account and all associated data."""
    require_admin(req.admin_username)
    try:
        ok = await asyncio.to_thread(audit_store.delete_user, target_username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail=f"账号「{target_username}」不存在")
    # Notify the user's WS connection if still waiting (e.g. on pending screen)
    await notify_manager.push(target_username, {"type": "rejected", "message": "账号注册申请已被拒绝"})
    return ApiResponse(success=True, message="账号已删除", data={"username": target_username})


@router.post("/users/{target_username}/approve", response_model=ApiResponse)
async def approve_user(target_username: str, req: AdminUserReviewRequest):
    """Admin: approve a pending registration — sets status to 'active'."""
    require_admin(req.admin_username)
    try:
        row = await asyncio.to_thread(
            audit_store.update_user,
            target_username,
            {"status": "active", "notes": req.note or ""},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail=f"账号「{target_username}」不存在")
    await notify_manager.push(target_username, {"type": "approved", "message": "注册申请已通过，您现在可以登录了"})
    return ApiResponse(success=True, message="账号已审核通过", data=row)


@router.post("/users/{target_username}/reject", response_model=ApiResponse)
async def reject_user(target_username: str, req: AdminUserReviewRequest):
    """Admin: reject a pending registration — sets status to 'rejected'."""
    require_admin(req.admin_username)
    try:
        row = await asyncio.to_thread(
            audit_store.update_user,
            target_username,
            {"status": "rejected", "notes": req.note or ""},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail=f"账号「{target_username}」不存在")
    await notify_manager.push(target_username, {"type": "rejected", "message": "注册申请已被拒绝，请联系管理员"})
    return ApiResponse(success=True, message="账号已拒绝", data=row)
