import json
from typing import Dict
from fastapi import WebSocket

class ConnectionManager:
    """
    Manages active WebSocket connections to handle real-time notifications 
    and instant Public Address (PA) network broadcasts.
    """
    def __init__(self):
        # Maps user IDs to their active WebSocket connection
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: str):
        """Pushes a notification to a specific user on the LAN network."""
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(json.dumps(message))

    async def broadcast(self, message: dict):
        """Pushes a high-priority message to all connected clients simultaneously."""
        for connection in self.active_connections.values():
            await connection.send_text(json.dumps(message))

manager = ConnectionManager()