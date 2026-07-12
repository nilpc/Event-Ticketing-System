"""NFR-6: Domain exception hierarchy."""


class BookingConflictError(Exception):
    """Raised when a booking operation conflicts with existing state (FR-8)."""


class SeatUnavailableError(Exception):
    """Raised when a requested seat is not AVAILABLE (FR-7)."""


class InvalidTokenError(Exception):
    """Raised when a queue or idempotency token is invalid (FR-6, FR-8)."""


class PersistenceError(Exception):
    """Raised on unexpected database failures during checkout (FR-8)."""


class NotFoundError(Exception):
    """Raised when a requested entity does not exist (FR-5)."""


class PaymentProviderError(Exception):
    """Raised when the payment provider returns an error (FR-5)."""
