"""Admin CRUD request/response schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from core.enums import EventType


# ── Event ──────────────────────────────────────────────────────────────
class EventCreate(BaseModel):
    event_type: EventType
    name: str = Field(max_length=255)
    description: str | None = None


class EventUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    event_type: EventType | None = None


# ── Venue ──────────────────────────────────────────────────────────────
class VenueCreate(BaseModel):
    name: str = Field(max_length=255)
    capacity: int = Field(ge=1)


class VenueUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    capacity: int | None = Field(default=None, ge=1)


# ── Showtime ───────────────────────────────────────────────────────────
class ShowtimeCreate(BaseModel):
    event_id: str
    venue_id: str
    base_price: Decimal = Field(decimal_places=2, ge=0)
    start_time: datetime
    end_time: datetime
    auto_seats: bool = True


class ShowtimeUpdate(BaseModel):
    base_price: Decimal | None = Field(default=None, decimal_places=2, ge=0)
    start_time: datetime | None = None
    end_time: datetime | None = None
