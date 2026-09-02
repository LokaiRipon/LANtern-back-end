import json
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}   # user_id -> ws
        self.room_members: Dict[str, Set[int]] = {}          # room_id -> set of user_ids

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        # Remove from all rooms
        for room in list(self.room_members.keys()):
            if user_id in self.room_members.get(room, set()):
                self.room_members[room].discard(user_id)

    async def send_personal(self, user_id: int, message: dict):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(json.dumps(message))
            except WebSocketDisconnect:
                self.disconnect(user_id)

    async def broadcast(self, message: dict):
        for user_id, ws in list(self.active_connections.items()):
            try:
                await ws.send_text(json.dumps(message))
            except WebSocketDisconnect:
                self.disconnect(user_id)

    async def send_to_room(self, room_id: str, message: dict, exclude_user: int = None):
        if room_id not in self.room_members:
            return
        for user_id in list(self.room_members[room_id]):
            if user_id == exclude_user:
                continue
            await self.send_personal(user_id, message)

    def join_room(self, room_id: str, user_id: int):
        if room_id not in self.room_members:
            self.room_members[room_id] = set()
        self.room_members[room_id].add(user_id)

    def leave_room(self, room_id: str, user_id: int):
        if room_id in self.room_members:
            self.room_members[room_id].discard(user_id)

manager = ConnectionManager()