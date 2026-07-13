"""FR-9: WebhookService — process Stripe payment callbacks (§6 Layer 3)."""

from __future__ import annotations

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import BookingStatus
from services.booking.repositories.booking_repo import BookingRepository
from services.booking.repositories.lock_repo import LockRepository
from services.booking.repositories.seat_repo import SeatRepository
from services.payment.providers.stripe_client import StripeClient
from services.payment.repositories.payment_repo import PaymentRepository

logger = structlog.get_logger()


class WebhookService:
    """FR-9: Process Stripe webhooks — §6 Layer 3 reference implementation."""

    def __init__(
        self,
        session: AsyncSession,
        booking_repo: BookingRepository,
        seat_repo: SeatRepository,
        lock_repo: LockRepository,
        payment_repo: PaymentRepository | None = None,
    ) -> None:
        self.session = session
        self.booking_repo = booking_repo
        self.seat_repo = seat_repo
        self.lock_repo = lock_repo
        self.payment_repo = payment_repo or PaymentRepository(session)
        self.provider = StripeClient()

    async def process_webhook(self, payload: bytes, signature: str) -> None:
        """FR-9: Process Stripe webhook event — §6 Layer 3."""
        try:
            event = self.provider.construct_webhook_event(payload, signature)
        except Exception as exc:
            logger.warning("webhook_signature_invalid", error=str(exc))
            raise ValueError("Invalid webhook signature.") from exc

        show_id = seat_id = user_id = None
        terminal = False

        try:
            async with self.session.begin():
                # §6: Idempotency guard — duplicate event_id raises IntegrityError
                try:
                    await self.booking_repo.log_webhook_event(
                        event.id, event.type, payload.decode()
                    )
                except IntegrityError:
                    return  # Duplicate — silently drop

                metadata = getattr(event.data.object, "metadata", {}) or {}
                booking_id_str = metadata.get("booking_id")
                if not booking_id_str:
                    return  # §6: null-check guard — spoofed/missing booking_id

                from uuid import UUID

                try:
                    booking_id = UUID(booking_id_str)
                except (ValueError, TypeError):
                    return

                show_id_str = metadata.get("show_id")
                seat_id_val = metadata.get("seat_id")
                user_id_str = metadata.get("user_id")

                if show_id_str:
                    show_id = UUID(show_id_str)
                if seat_id_val:
                    seat_id = seat_id_val
                if user_id_str:
                    user_id = UUID(user_id_str)

                booking = await self.booking_repo.get_booking_by_id(booking_id)

                # §6: Null check to prevent AttributeError on spoofed webhooks
                if not booking:
                    return

                if event.type == "payment_intent.succeeded":
                    # §6: Update payment record status
                    await self.payment_repo.update_payment_status_by_intent(
                        event.data.object.id, "succeeded"
                    )
                    if booking.status == BookingStatus.FAILED:
                        # §6: Late-webhook guard — sweeper beat us
                        await self.booking_repo.add_outbox_event(
                            aggregate_type="Payment",
                            aggregate_id=booking_id,
                            event_type="REFUND_REQUIRED",
                            payload={
                                "reason": "Late webhook on failed booking",
                                "booking_id": str(booking_id),
                            },
                        )
                    elif booking.status == BookingStatus.PENDING:
                        if show_id is None or seat_id is None:
                            return  # §6: missing metadata — cannot finalize
                        await self.seat_repo.finalize_sold_seat(show_id, seat_id)
                        await self.booking_repo.update_booking_status(
                            booking_id,
                            BookingStatus.CONFIRMED,
                            correlation_id=event.data.object.id,
                            source="webhook",
                        )
                        await self.booking_repo.add_outbox_event(
                            aggregate_type="Booking",
                            aggregate_id=booking_id,
                            event_type="BOOKING_CONFIRMED",
                            payload={
                                "booking_id": str(booking_id),
                                "show_id": str(show_id),
                                "seat_id": seat_id,
                            },
                        )
                        terminal = True
                    # else: already CONFIRMED/FAILED — intermediate or stale event

                elif event.type in (
                    "payment_intent.payment_failed",
                    "payment_intent.canceled",
                ):
                    # §6: Update payment record status
                    await self.payment_repo.update_payment_status_by_intent(
                        event.data.object.id, "failed"
                    )
                    if booking.status == BookingStatus.PENDING:
                        if show_id is None or seat_id is None:
                            return  # §6: missing metadata — cannot revert
                        await self.seat_repo.revert_seat_to_available(
                            show_id, seat_id
                        )
                        await self.booking_repo.update_booking_status(
                            booking_id,
                            BookingStatus.FAILED,
                            source="webhook",
                        )
                        terminal = True
                    # else: already non-PENDING — nothing to revert

        except IntegrityError:
            # Defensive: duplicate event raced past the inner guard
            return

        # §6: Redis cleanup stays OUTSIDE the DB transaction, gated to
        # terminal outcomes only — prevents broken state on partial failure.
        if terminal and show_id is not None and seat_id is not None and user_id is not None:
            await self.lock_repo.release_seat_lock_safe(show_id, seat_id, user_id)
            await self.lock_repo.release_user_hold_limit(show_id, user_id)
