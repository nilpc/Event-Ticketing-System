"""NFR-6: Domain exception hierarchy.

Inherit from standard Python exceptions so FastAPI routers can catch
them with familiar patterns: LookupError → 404, ValueError → 409, etc.
"""


class BookingConflictError(ValueError):
    """Raised when a booking operation conflicts with existing state (FR-8)."""


class SeatUnavailableError(ValueError):
    """Raised when a requested seat is not AVAILABLE (FR-7)."""


class InvalidTokenError(ValueError):
    """Raised when a queue or idempotency token is invalid (FR-6, FR-8)."""


class PersistenceError(OSError):
    """Raised on unexpected database failures during checkout (FR-8)."""


class NotFoundError(LookupError):
    """Raised when a requested entity does not exist (FR-5)."""


class PaymentProviderError(OSError):
    """Raised when the payment provider returns an error (FR-5)."""


class WeakPasswordError(ValueError):
    """Raised when a password fails zxcvbn strength validation (FR-1)."""


class RedisUnavailableError(OSError):
    """Raised when Redis is unavailable and a lock operation cannot proceed."""
