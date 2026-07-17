"""FR-7: Pydantic schemas for seat lock endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SeatLockRequest(BaseModel):
    """FR-7: Request to lock one or more seats."""

    show_id: UUID
    seat_ids: list[str]


class SeatLockResponse(BaseModel):
    """FR-7: Seat lock confirmation with server-generated idempotency key."""

    idempotency_key: str
    expires_at: datetime
    locked_seat_ids: list[str]
