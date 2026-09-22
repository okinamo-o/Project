import asyncio
import json
import logging
from typing import List, Dict, Any
from fastapi import WebSocket

logger = logging.getLogger("nexus.events")

class ConnectionManager:
    """Manages active WebSocket connections and broadcasts telemetry, incidents, and events."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info(f"[WS] Client connected. Total active: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info(f"[WS] Client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a structured JSON event to all connected clients."""
        payload = json.dumps(message)
        async with self._lock:
            dead_connections = []
            for connection in self.active_connections:
                try:
                    await connection.send_text(payload)
                except Exception as e:
                    logger.warning(f"[WS] Failed to send message: {e}")
                    dead_connections.append(connection)
            for dead in dead_connections:
                if dead in self.active_connections:
                    self.active_connections.remove(dead)

# Global singleton event bus
event_manager = ConnectionManager()
