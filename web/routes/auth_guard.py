# -*- coding: utf-8 -*-
"""Request guards for user-attributed write operations."""

from contextvars import ContextVar

from fastapi import HTTPException

from web.services.audit_store import audit_store


current_username: ContextVar[str] = ContextVar("mockapi_current_username", default="")


def require_valid_username(username: str | None) -> str:
    username = (username or "").strip()
    if not username:
        raise HTTPException(status_code=403, detail="请先登录账号再继续操作")
    if not audit_store.user_exists(username):
        raise HTTPException(status_code=403, detail="登录账号无效，请重新登录")
    current_username.set(username)
    return username


def require_admin(username: str | None) -> str:
    """Validate caller and enforce admin role."""
    caller = require_valid_username(username)
    role = audit_store.get_user_role(caller)
    if role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")
    return caller
