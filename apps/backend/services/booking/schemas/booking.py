"""FR-8: Pydantic schemas for booking endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class BookRequest(BaseModel):
    """FR-8: Request to initialize a booking for one or more seats."""

    show_id: UUID
    seat_ids: list[str]
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
    seat_ids: list[str]


class BookingSeatInfo(BaseModel):
    """A single seat in a booking."""

    seat_id: str
    tier: str
    price: str


class BookingListItem(BaseModel):
    """A user's booking with event/venue details."""

    booking_id: str
    status: str
    seats: list[BookingSeatInfo]
    amount: str
    currency: str
    created_at: str | None = None
    show_id: str
    start_time: str | None = None
    end_time: str | None = None
    event_name: str
    venue_name: str
