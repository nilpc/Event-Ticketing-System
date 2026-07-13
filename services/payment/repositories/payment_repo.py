"""FR-5: Repository for payment record persistence."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from services.booking.models.payment import Payment


class PaymentRepository:
    """Handles booking.payments — SRP, NFR-6."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_payment_record(
        self,
        payment_id: UUID,
        booking_id: UUID,
        amount: Decimal,
        status: str,
    ) -> None:
        """FR-5: Write initiated record before calling Stripe."""
        payment = Payment(
            payment_id=payment_id,
            booking_id=booking_id,
            provider="stripe",
            amount=amount,
            status=status,
        )
        self.session.add(payment)
        await self.session.flush()

    async def update_payment_record(
        self,
        payment_id: UUID,
        provider_payment_id: str | None = None,
        status: str | None = None,
    ) -> None:
        """FR-5: Update record after Stripe responds."""
        values: dict = {}
        if provider_payment_id is not None:
            values["provider_payment_id"] = provider_payment_id
        if status is not None:
            values["status"] = status
        if values:
            await self.session.execute(
                update(Payment).where(Payment.payment_id == payment_id).values(**values)
            )

    async def get_active_payment_for_booking(self, booking_id: UUID) -> Payment | None:
        """FR-5: Fetch existing non-terminal intent to prevent duplicates.

        Backed by unique_active_payment_per_booking partial index.
        Terminal statuses: succeeded, failed, refunded.
        """
        terminal_statuses = ("succeeded", "failed", "refunded")
        result = await self.session.execute(
            select(Payment).where(
                and_(
                    Payment.booking_id == booking_id,
                    ~Payment.status.in_(terminal_statuses),
                )
            )
        )
        return result.scalar_one_or_none()

    async def update_payment_status_by_intent(self, provider_payment_id: str, status: str) -> None:
        """FR-5: Webhook handler — update status by Stripe intent ID."""
        await self.session.execute(
            update(Payment)
            .where(Payment.provider_payment_id == provider_payment_id)
            .values(status=status)
        )
