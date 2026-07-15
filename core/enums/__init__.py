"""NFR-6: Python Enums for domain state machines."""

import enum


class EventType(enum.StrEnum):
    """booking.events.event_type — differentiates movies from live events."""

    MOVIE = "MOVIE"
    EVENT = "EVENT"


class SeatStatus(enum.StrEnum):
    """booking.seats.status — FR-7 seat lifecycle."""

    AVAILABLE = "AVAILABLE"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    SOLD = "SOLD"


class BookingStatus(enum.StrEnum):
    """booking.bookings.status — FR-8, FR-9 booking lifecycle."""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PaymentStatus(enum.StrEnum):
    """booking.payments.status — FR-5 payment lifecycle."""

    INITIATED = "initiated"
    REQUIRES_ACTION = "requires_action"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
