from fastapi import WebSocket
from typing import Dict, List


class WebSocketManager:
    def __init__(self):
        self._connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, conversation_id: str, ws: WebSocket):
        await ws.accept()
        self._connections.setdefault(conversation_id, []).append(ws)

    async def disconnect(self, conversation_id: str, ws: WebSocket):
        conns = self._connections.get(conversation_id, [])
        if ws in conns:
            conns.remove(ws)

    async def send_event(self, conversation_id: str, event: dict):
        conns = self._connections.get(conversation_id, [])
        for ws in conns[:]:
            try:
                await ws.send_json(event)
            except Exception:
                conns.remove(ws)


ws_manager = WebSocketManager()
