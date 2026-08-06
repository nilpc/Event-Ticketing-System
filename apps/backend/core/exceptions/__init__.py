class BookingConflictError(ValueError):
    pass

class SeatUnavailableError(ValueError):
    pass

class InvalidTokenError(ValueError):
    pass

class PersistenceError(OSError):
    pass

class NotFoundError(LookupError):
    pass

class PaymentProviderError(OSError):
    pass

class WeakPasswordError(ValueError):
    pass

class RedisUnavailableError(OSError):
    pass
