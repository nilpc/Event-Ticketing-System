"""FR-5: Stripe API wrapper — PCI-compliant payment intent operations."""

from __future__ import annotations

import asyncio

import stripe
import structlog

from core.config import settings
from core.exceptions import PaymentProviderError

logger = structlog.get_logger()


class StripeClient:
    """FR-5: Thin wrapper around Stripe SDK for payment intents.

    All blocking Stripe SDK calls are dispatched via asyncio.to_thread()
    to avoid freezing the event loop.
    """

    def __init__(self) -> None:
        stripe.api_key = settings.STRIPE_SECRET_KEY

    async def create_payment_intent(
        self,
        amount_cents: int,
        currency: str,
        metadata: dict | None = None,
    ) -> stripe.PaymentIntent:
        """FR-5: Create a Stripe PaymentIntent."""
        try:
            intent = await asyncio.to_thread(
                stripe.PaymentIntent.create,
                amount=amount_cents,
                currency=currency,
                metadata=metadata or {},
                automatic_payment_methods={"enabled": True},
            )
            logger.info(
                "stripe_intent_created",
                intent_id=intent.id,
                amount=amount_cents,
                currency=currency,
            )
            return intent
        except stripe.StripeError as exc:
            logger.error("stripe_intent_creation_failed", error=str(exc))
            raise PaymentProviderError(f"Stripe error: {exc.user_message}") from exc

    async def cancel_payment_intent(self, intent_id: str) -> None:
        """FR-5: Cancel a Stripe PaymentIntent."""
        try:
            await asyncio.to_thread(stripe.PaymentIntent.cancel, intent_id)
            logger.info("stripe_intent_cancelled", intent_id=intent_id)
        except stripe.StripeError as exc:
            logger.error("stripe_intent_cancel_failed", intent_id=intent_id, error=str(exc))

    async def retrieve_payment_intent(self, intent_id: str) -> stripe.PaymentIntent:
        """FR-5: Retrieve an existing PaymentIntent (e.g. to get client_secret for reuse)."""
        try:
            intent = await asyncio.to_thread(stripe.PaymentIntent.retrieve, intent_id)
            return intent
        except stripe.StripeError as exc:
            logger.error("stripe_intent_retrieve_failed", intent_id=intent_id, error=str(exc))
            raise PaymentProviderError(f"Stripe retrieve error: {exc.user_message}") from exc

    def construct_webhook_event(
        self,
        payload: bytes,
        sig_header: str,
    ) -> stripe.Event:
        """FR-5: Verify and construct a Stripe webhook event."""
        return stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET,
        )
