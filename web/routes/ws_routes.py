# -*- coding: utf-8 -*-
"""WebSocket 路由：实时日志推送 + 用户通知"""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from web.services.log_capture import ws_log_handler
from web.services.notify_manager import notify_manager

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/logs/{session_id}")
async def websocket_logs(websocket: WebSocket, session_id: str):
    """WebSocket 实时日志推送"""
    await websocket.accept()
    queue = ws_log_handler.register_session(session_id)
    try:
        while True:
            log_entry = await queue.get()
            await websocket.send_text(json.dumps(log_entry, ensure_ascii=False))
    except WebSocketDisconnect:
        pass
    finally:
        ws_log_handler.unregister_session(session_id)


@router.websocket("/ws/notify/{username}")
async def websocket_notify(websocket: WebSocket, username: str):
    """Per-user push notifications (account approval / rejection)."""
    await websocket.accept()
    queue = notify_manager.register(username)
    try:
        while True:
            message = await queue.get()
            await websocket.send_text(json.dumps(message, ensure_ascii=False))
    except WebSocketDisconnect:
        pass
    finally:
        notify_manager.unregister(username)

