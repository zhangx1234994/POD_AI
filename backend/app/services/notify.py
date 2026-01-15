"""简单的通知服务，基于内存/Redis。"""

from collections import deque
from typing import Deque

from fastapi import WebSocket


class NotificationService:
    def __init__(self) -> None:
        self.connections: list[WebSocket] = []
        self.recent_events: Deque[dict] = deque(maxlen=100)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.connections:
            self.connections.remove(websocket)

    async def broadcast(self, event: dict) -> None:
        self.recent_events.append(event)
        for conn in list(self.connections):
            await conn.send_json(event)

    async def replay(self, websocket: WebSocket) -> None:
        for event in self.recent_events:
            await websocket.send_json(event)


notify_service = NotificationService()
