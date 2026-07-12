"""FR-7, FR-8, FR-10: Repository for seat state transitions and price lookups."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


class SeatRepository:
    """Handles booking.seats queries — SRP, NFR-6."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def transition_seat_to_pending(self, show_id: UUID, seat_id: str) -> None:
        """FR-8: Atomically transition seat from AVAILABLE to PENDING_PAYMENT."""
        ...

    async def get_seat_price(self, show_id: UUID, seat_id: str) -> Decimal:
        """FR-10: Read true seat price for server-side amount calculation."""
        ...

    async def finalize_sold_seat(self, show_id: UUID, seat_id: str) -> None:
        """FR-8: Transition PENDING_PAYMENT to SOLD after payment confirmation."""
        ...

    async def revert_seat_to_available(self, show_id: UUID, seat_id: str) -> None:
        """FR-9: Revert seat to AVAILABLE on payment failure or sweeper."""
        ...
