# Feature 3: WebSocket for Live Seat Availability

**Status:** Proposed
**Priority:** Medium
**Owner:** Full-stack
**Estimated Effort:** 4-6 days

## Overview

Real-time seat map updates using WebSockets, powered by Redis Pub/Sub.

## Goals

- Instant visibility of seat locks/bookings to all users.
- Reduced polling overhead.
- Modern, engaging UX for high-demand events.

## Requirements

- Authenticated WebSocket connections.
- Broadcast seat status changes.
- Graceful reconnection and fallback to polling.

## Implementation Plan

### Backend (Gateway)

```python
# apps/backend/services/gateway/websocket.py
@app.websocket("/ws/showtime/{showtime_id}")
async def websocket_endpoint(websocket: WebSocket, showtime_id: int, token: str):
    await authenticate_websocket(token)  # Reuse JWT logic
    await manager.connect(websocket, showtime_id)
    try:
        while True:
            await websocket.receive_text()  # Keep alive
    finally:
        manager.disconnect(...)
```

### Broadcasting (Booking Service)

```python
# After successful lock/book
await redis.publish(f"showtime:{showtime_id}:seats", json.dumps(update_data))
```

### Frontend

```tsx
// apps/web/src/components/seat-map.tsx
useEffect(() => {
  const ws = new WebSocket(`/ws/showtime/${id}?token=${jwt}`);
  ws.onmessage = (event) => {
    const update = JSON.parse(event.data);
    updateSeatMap(update); // Optimistic UI update
  };
}, []);
```

### Connection Manager

Simple in-memory + Redis backplane for multi-instance scaling.

## Testing

- Manual + automated WS tests.
- Simulate concurrent users with load tools.

## Edge Cases

- High number of connections (monitor memory).
- Network drops -> auto-reconnect.
- Auth expiration during session.

## Benefits

Significantly improved user experience and reduced server load.
