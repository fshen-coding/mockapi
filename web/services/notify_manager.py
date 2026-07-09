# -*- coding: utf-8 -*-
"""Per-user real-time notification service via WebSocket.

Each authenticated client that needs to receive push notifications connects to
``/ws/notify/{username}`` and registers a queue here.  The admin approval
endpoints push a single JSON message then the queue is drained and closed.
"""
from __future__ import annotations

import asyncio
from typing import Any


class UserNotifyManager:
    """In-memory store of per-username asyncio queues."""

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue] = {}

    def register(self, username: str) -> asyncio.Queue:
        """Return (creating if needed) the notification queue for *username*."""
        if username not in self._queues:
            self._queues[username] = asyncio.Queue(maxsize=20)
        return self._queues[username]

    def unregister(self, username: str) -> None:
        self._queues.pop(username, None)

    async def push(self, username: str, payload: dict[str, Any]) -> None:
        """Push *payload* to the registered queue for *username*, if any."""
        queue = self._queues.get(username)
        if queue is None:
            return
        try:
            await queue.put(payload)
        except asyncio.QueueFull:
            pass


# Global singleton — imported by ws_routes and admin_routes
notify_manager = UserNotifyManager()
