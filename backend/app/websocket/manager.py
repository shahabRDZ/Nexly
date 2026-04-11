import uuid
import json
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections per user.

    Each user can have multiple connections (e.g., phone + web).
    Messages are broadcast to all active connections for a user.
    """

    def __init__(self):
        # user_id -> set of WebSocket connections
        self._connections: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: uuid.UUID, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[user_id].add(ws)
        logger.info("User %s connected (total: %d)", user_id, len(self._connections[user_id]))

    def disconnect(self, user_id: uuid.UUID, ws: WebSocket) -> None:
        self._connections[user_id].discard(ws)
        if not self._connections[user_id]:
            del self._connections[user_id]
        logger.info("User %s disconnected", user_id)

    def is_online(self, user_id: uuid.UUID) -> bool:
        return user_id in self._connections and len(self._connections[user_id]) > 0

    async def send_to_user(self, user_id: uuid.UUID, event: str, data: dict) -> bool:
        """Send event to all connections of a user. Returns True if user was online."""
        connections = self._connections.get(user_id, set())
        if not connections:
            return False

        payload = json.dumps({"event": event, "data": data})
        dead = []
        for ws in connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        for ws in dead:
            connections.discard(ws)

        return len(connections) > 0

    async def broadcast_presence(self, user_id: uuid.UUID, is_online: bool) -> None:
        """Notify all connected users about presence change."""
        payload = {
            "user_id": str(user_id),
            "is_online": is_online,
        }
        for uid in list(self._connections.keys()):
            if uid != user_id:
                await self.send_to_user(uid, "presence", payload)


# Singleton instance
manager = ConnectionManager()
