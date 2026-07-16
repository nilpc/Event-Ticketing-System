"""Outbox relay worker — publish outbox events with FOR UPDATE SKIP LOCKED."""

from __future__ import annotations

import asyncio

import structlog

from core.db.session import async_session_factory
from services.booking.repositories.booking_repo import BookingRepository

logger = structlog.get_logger()

RELAY_INTERVAL_SECONDS = 5


async def publish_outbox_events() -> None:
    """Poll outbox and 'publish' (log) unpublished events."""
    async with async_session_factory() as session:
        booking_repo = BookingRepository(session)

        async with session.begin():
            events = await booking_repo.get_unpublished_outbox_events_for_update_skip_locked()
            for event in events:
                # Phase 3: log only. Phase 6: real message broker.
                logger.info(
                    "outbox_event_published",
                    event_id=str(event.event_id),
                    event_type=event.event_type,
                    aggregate_type=event.aggregate_type,
                )
                await booking_repo.mark_outbox_published(event.event_id)


async def run_relay() -> None:
    """Background loop — poll outbox every 5 seconds."""
    logger.info("outbox_relay_started", interval=RELAY_INTERVAL_SECONDS)
    while True:
        try:
            await publish_outbox_events()
        except Exception as exc:
            logger.error("relay_iteration_failed", error=str(exc))
        await asyncio.sleep(RELAY_INTERVAL_SECONDS)
