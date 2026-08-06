from __future__ import annotations
import asyncio
import structlog
from core.db.session import async_session_factory
from services.booking.repositories.booking_repo import BookingRepository
logger = structlog.get_logger()
RELAY_FALLBACK_INTERVAL = 5.0
_notify_event = asyncio.Event()

async def publish_outbox_events() -> int:
    published_count = 0
    async with async_session_factory() as session:
        booking_repo = BookingRepository(session)
        async with session.begin():
            events = await booking_repo.get_unpublished_outbox_events_for_update_skip_locked()
            for event in events:
                logger.info('outbox_event_published', event_id=str(event.event_id), event_type=event.event_type, aggregate_type=event.aggregate_type)
                await booking_repo.mark_outbox_published(event.event_id)
                published_count += 1
    return published_count

async def _listen_postgres_notifications() -> None:
    while True:
        try:
            async with async_session_factory() as session:
                connection = await session.connection()
                raw_conn = await connection.get_raw_connection()
                driver_conn = getattr(raw_conn, 'driver_connection', None)
                if driver_conn and hasattr(driver_conn, 'add_listener'):
                    await driver_conn.add_listener('outbox_inserted', lambda *args: _notify_event.set())
                    logger.info('outbox_listen_subscribed', channel='outbox_inserted')
                    while True:
                        await asyncio.sleep(3600)
                else:
                    break
        except Exception as exc:
            logger.warning('outbox_listen_retry', error=str(exc))
            await asyncio.sleep(5)

async def run_relay() -> None:
    logger.info('outbox_relay_started', mode='LISTEN/NOTIFY', fallback_interval=RELAY_FALLBACK_INTERVAL)
    asyncio.create_task(_listen_postgres_notifications())
    while True:
        try:
            await publish_outbox_events()
            _notify_event.clear()
        except Exception as exc:
            logger.error('relay_iteration_failed', error=str(exc))
        try:
            await asyncio.wait_for(_notify_event.wait(), timeout=RELAY_FALLBACK_INTERVAL)
        except TimeoutError:
            pass
