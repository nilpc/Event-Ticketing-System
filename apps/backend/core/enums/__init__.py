import enum


class EventType(enum.StrEnum):
    MOVIE = 'MOVIE'
    EVENT = 'EVENT'

class SeatStatus(enum.StrEnum):
    AVAILABLE = 'AVAILABLE'
    PENDING_PAYMENT = 'PENDING_PAYMENT'
    SOLD = 'SOLD'

class BookingStatus(enum.StrEnum):
    PENDING = 'PENDING'
    CONFIRMED = 'CONFIRMED'
    FAILED = 'FAILED'
    CANCELLED = 'CANCELLED'

class PaymentStatus(enum.StrEnum):
    INITIATED = 'initiated'
    REQUIRES_ACTION = 'requires_action'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    REFUNDED = 'refunded'
