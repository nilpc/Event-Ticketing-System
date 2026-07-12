"""FR-5: Repository for payment record persistence."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


class PaymentRepository:
    """Handles booking.payments — SRP, NFR-6."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_payment_record(
        self,
        payment_id: UUID,
        booking_id: UUID,
        amount: object,
        status: str,
    ) -> None:
        """FR-5: Write initiated record before calling Stripe."""
        ...

    async def update_payment_record(
        self,
        payment_id: UUID,
        provider_payment_id: str | None = None,
        status: str | None = None,
    ) -> None:
        """FR-5: Update record after Stripe responds."""
        ...

    async def get_active_payment_for_booking(self, booking_id: UUID) -> object | None:
        """FR-5: Fetch existing non-terminal intent to prevent duplicates.

        Backed by unique_active_payment_per_booking partial index (FR-5).
        """
        ...

    async def update_payment_status_by_intent(
        self, provider_payment_id: str, status: str
    ) -> None:
        """FR-5: Webhook handler — update status by Stripe intent ID."""
        ...
