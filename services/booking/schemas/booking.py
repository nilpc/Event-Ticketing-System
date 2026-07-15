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


class MockConfirmResponse(BaseModel):
    """Demo-only: booking confirmed without real payment."""

    booking_id: UUID
    status: str
    seat_status: str


class BookingListItem(BaseModel):
    """A user's booking with event/venue details."""

    booking_id: str
    status: str
    seat_id: str
    amount: str
    currency: str
    created_at: str | None = None
    show_id: str
    start_time: str | None = None
    end_time: str | None = None
    event_name: str
    venue_name: str
