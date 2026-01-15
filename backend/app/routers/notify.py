"""Notification 路由：提供 WebSocket/SSE。"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.notify import notify_service

router = APIRouter()


@router.websocket("/api/notify/v1/stream")
async def websocket_stream(websocket: WebSocket) -> None:
    await notify_service.connect(websocket)
    try:
        await notify_service.replay(websocket)
        while True:
            data = await websocket.receive_text()
            await notify_service.broadcast({"type": "echo", "payload": data})
    except WebSocketDisconnect:
        notify_service.disconnect(websocket)


@router.post("/api/notify/v1/event")
async def push_event(event: dict) -> dict:
    await notify_service.broadcast(event)
    return {"success": True}
