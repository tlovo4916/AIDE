from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.types import WSFrame, WSFrameType

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, project_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(project_id, []).append(ws)

    def disconnect(self, project_id: str, ws: WebSocket) -> None:
        conns = self._connections.get(project_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self._connections.pop(project_id, None)

    async def send_response(
        self,
        ws: WebSocket,
        event: str,
        payload: dict[str, Any],
        request_id: str | None = None,
    ) -> None:
        frame = WSFrame(
            type=WSFrameType.RESPONSE,
            event=event,
            payload=payload,
            request_id=request_id,
        )
        await ws.send_json(frame.model_dump(mode="json"))

    async def broadcast(
        self,
        project_id: str,
        event: str,
        payload: dict[str, Any],
    ) -> None:
        frame = WSFrame(
            type=WSFrameType.PUSH,
            event=event,
            payload=payload,
        )
        data = frame.model_dump(mode="json")
        dead: list[WebSocket] = []
        for ws in self._connections.get(project_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(project_id, ws)

    def active_connections(self, project_id: str) -> int:
        return len(self._connections.get(project_id, []))


manager = ConnectionManager()


async def _handle_request(
    ws: WebSocket,
    project_id: str,
    frame: WSFrame,
) -> None:
    event = frame.event
    payload = frame.payload
    request_id = frame.request_id

    if event == "ping":
        await manager.send_response(ws, "pong", {}, request_id)
    elif event == "subscribe":
        await manager.send_response(
            ws,
            "subscribed",
            {"project_id": project_id},
            request_id,
        )
    else:
        await manager.send_response(
            ws,
            "error",
            {"message": f"Unknown event: {event}"},
            request_id,
        )


@router.websocket("/ws/projects/{project_id}")
async def websocket_endpoint(ws: WebSocket, project_id: str) -> None:
    await manager.connect(project_id, ws)
    try:
        while True:
            raw = await ws.receive_json()
            try:
                frame = WSFrame.model_validate(raw)
            except Exception:
                await manager.send_response(
                    ws, "error", {"message": "Invalid frame format"}
                )
                continue

            if frame.type == WSFrameType.REQUEST:
                await _handle_request(ws, project_id, frame)
            else:
                await manager.send_response(
                    ws,
                    "error",
                    {"message": "Clients may only send REQUEST frames"},
                )
    except WebSocketDisconnect:
        manager.disconnect(project_id, ws)
