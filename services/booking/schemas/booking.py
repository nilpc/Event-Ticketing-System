"""FR-8: Pydantic schemas for booking endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class BookRequest(BaseModel):
    """FR-8: Request to initialize a booking."""

    show_id: UUID
    seat_id: str
    idempotency_key: str  # server-generated from /seats/lock


class BookResponse(BaseModel):
    """FR-8: Booking initialization confirmation."""

    booking_id: UUID
    status: str
    expires_at: datetime
