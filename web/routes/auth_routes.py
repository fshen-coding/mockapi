# -*- coding: utf-8 -*-
"""User auth routes backed by PostgreSQL."""
from fastapi import APIRouter, HTTPException

from web.models.requests import AuthRequest
from web.models.responses import ApiResponse
from web.services.audit_store import audit_store

router = APIRouter(prefix="/api/auth", tags=["用户"])


@router.post("/register", response_model=ApiResponse)
async def register_user(req: AuthRequest):
    try:
        user = audit_store.register_user(req.username, req.password)
        return ApiResponse(
            success=True,
            message="注册成功，等待管理员审核",
            data={"username": user["username"], "role": user["role"], "status": user.get("status", "pending")},
        )
    except ValueError as exc:
        return ApiResponse(success=False, message=str(exc), data={"success": False, "error_message": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"注册失败: {exc}") from exc


@router.post("/login", response_model=ApiResponse)
async def login_user(req: AuthRequest):
    try:
        user = audit_store.authenticate_user(req.username, req.password)
    except PermissionError as exc:
        status = str(exc)
        if status == "pending":
            return ApiResponse(
                success=False,
                message="__pending__",
                data={"success": False, "status": "pending", "username": req.username},
            )
        if status == "rejected":
            return ApiResponse(
                success=False,
                message="注册申请已被拒绝，请联系管理员",
                data={"success": False, "status": "rejected"},
            )
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"登录失败: {exc}") from exc
    if not user:
        return ApiResponse(success=False, message="账号或密码不正确，请先注册或重新输入", data={"success": False})
    return ApiResponse(success=True, message="登录成功", data=user)

