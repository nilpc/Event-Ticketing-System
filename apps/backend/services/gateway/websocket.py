"""FR-7: WebSocket endpoint for live seat availability updates."""

from __future__ import annotations

import asyncio
import json

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError

from services.gateway.websocket_manager import manager

logger = structlog.get_logger()

ws_router = APIRouter()


def _verify_ws_token(token: str) -> str | None:
    """Verify JWT and return user_id. Returns None if invalid."""
    try:
        from core.security.jwt import decode_access_token
        claims = decode_access_token(token)
        return claims.get("sub")
    except (JWTError, Exception):
        return None


@ws_router.websocket("/ws/showtime/{show_id}")
async def websocket_seat_updates(
    websocket: WebSocket,
    show_id: str,
    token: str = "",
) -> None:
    """FR-7: WebSocket endpoint for real-time seat status broadcasting.

    Clients connect with a valid JWT as a query parameter:
        ws://localhost:8000/ws/showtime/{show_id}?token={jwt}

    The server pushes seat status changes as JSON messages:
        {
            "type": "seat_update",
            "seat_id": "A1",
            "status": "SOLD",
            "locked_by": "user-uuid"  // or null for SOLD
        }
    """
    # Authenticate
    user_id = _verify_ws_token(token)
    if not user_id:
        await websocket.close(code=4001, reason="Invalid or missing token")
        return

    await manager.connect(websocket, show_id)

    # Start Redis Pub/Sub listener in background
    pubsub_task = asyncio.create_task(_listen_redis(websocket, show_id))

    try:
        # Keep connection alive, handle pings
        while True:
            data = await websocket.receive_text()
            # Client can send pings or other messages
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        pubsub_task.cancel()
        await manager.disconnect(websocket, show_id)


async def _listen_redis(websocket: WebSocket, show_id: str) -> None:
    """Subscribe to Redis Pub/Sub channel for seat updates and forward to WebSocket."""
    from core.redis import get_redis

    try:
        redis = get_redis()
        pubsub = redis.pubsub()
        channel = f"showtime:{show_id}:seats"
        await pubsub.subscribe(channel)

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await websocket.send_text(json.dumps(data))
                except Exception:
                    pass  # Client may have disconnected

        await pubsub.unsubscribe(channel)
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.warning("redis_pubsub_error", show_id=show_id)
