"""Admin CRUD request/response schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from core.enums import EventType
from services.booking.schemas.catalog import EventResponse


# ── Event ──────────────────────────────────────────────────────────────
class EventCreate(BaseModel):
    event_type: EventType
    name: str = Field(max_length=255)
    description: str | None = None


class EventUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    event_type: EventType | None = None


class AdminEventResponse(EventResponse):
    """Event view for admins — includes owner so merchants can see their own.

    Deliberately NOT exposed on the public catalog (FR-4, NFR-2).
    """

    created_by: UUID | None = None


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

    @model_validator(mode="after")
    def validate_time_order(self) -> "ShowtimeCreate":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class ShowtimeUpdate(BaseModel):
    base_price: Decimal | None = Field(default=None, decimal_places=2, ge=0)
    start_time: datetime | None = None
    end_time: datetime | None = None

    @model_validator(mode="after")
    def validate_time_order(self) -> "ShowtimeUpdate":
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError("start_time must be before end_time")
        return self


# ── User Promotion ───────────────────────────────────────────────────────
class UserPromoteResponse(BaseModel):
    user_id: str
    email: str
    is_admin: bool
    is_master_admin: bool = False
