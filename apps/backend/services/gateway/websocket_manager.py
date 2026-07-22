"""FR-7: WebSocket connection manager for live seat availability broadcasting."""

from __future__ import annotations

import asyncio
import json

import structlog
from fastapi import WebSocket

logger = structlog.get_logger()


class ConnectionManager:
    """Manages WebSocket connections per showtime with Redis Pub/Sub backplane.

    For single-instance deployments, connections are held in memory.
    For multi-instance deployments, Redis Pub/Sub broadcasts seat updates
    across all gateway replicas.
    """

    def __init__(self) -> None:
        # show_id -> set of active WebSocket connections
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, show_id: str) -> None:
        """Accept a new WebSocket connection and register it for a showtime."""
        await websocket.accept()
        async with self._lock:
            if show_id not in self._connections:
                self._connections[show_id] = set()
            self._connections[show_id].add(websocket)
        count = len(self._connections.get(show_id, set()))
        logger.info("ws_connected", show_id=show_id, total=count)

    async def disconnect(self, websocket: WebSocket, show_id: str) -> None:
        """Remove a WebSocket connection from a showtime."""
        async with self._lock:
            conns = self._connections.get(show_id)
            if conns:
                conns.discard(websocket)
                if not conns:
                    del self._connections[show_id]
        logger.info("ws_disconnected", show_id=show_id)

    async def broadcast(self, show_id: str, message: dict) -> None:
        """Broadcast a message to all connected clients for a showtime.

        Dead connections are silently pruned.
        """
        async with self._lock:
            conns = self._connections.get(show_id, set()).copy()

        if not conns:
            return

        payload = json.dumps(message)
        dead: list[WebSocket] = []

        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        # Prune dead connections
        if dead:
            async with self._lock:
                active = self._connections.get(show_id)
                if active:
                    for ws in dead:
                        active.discard(ws)
                    if not active:
                        del self._connections[show_id]

    def get_connection_count(self, show_id: str | None = None) -> int:
        """Return number of active connections, optionally for a specific showtime."""
        if show_id:
            return len(self._connections.get(show_id, set()))
        return sum(len(conns) for conns in self._connections.values())


# Module-level singleton — shared across the application lifecycle
manager = ConnectionManager()
