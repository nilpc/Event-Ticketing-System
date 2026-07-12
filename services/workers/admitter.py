"""NFR-3: Queue Admitter — admits users from queue at a fixed rate."""

from __future__ import annotations

import asyncio
from uuid import UUID

import structlog

from services.booking.repositories.lock_repo import LockRepository

logger = structlog.get_logger()

# NFR-3: Admit N users per cycle
ADMIT_BATCH_SIZE = 10
ADMIT_INTERVAL_SECONDS = 2


async def run_admitter() -> None:
    """NFR-3: Background loop — admit users from queue at fixed rate."""
    logger.info(
        "admitter_started",
        interval=ADMIT_INTERVAL_SECONDS,
        batch=ADMIT_BATCH_SIZE,
    )
    while True:
        try:
            await admit_batch()
        except Exception as exc:
            logger.error("admitter_iteration_failed", error=str(exc))
        await asyncio.sleep(ADMIT_INTERVAL_SECONDS)


async def admit_batch() -> None:
    """Pop oldest users from queue sorted sets and admit them."""
    lock_repo = LockRepository()

    try:
        from core.redis import get_redis

        redis = get_redis()
    except Exception:
        return

    # Find all queue sorted sets
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor, match="queue:*", count=100)
        for key in keys:
            if isinstance(key, bytes):
                key = key.decode()
            # Skip non-queue keys (e.g. queue:session:xxx)
            parts = key.split(":")
            if len(parts) != 2:
                continue
            show_id = parts[1]

            # Pop oldest users from sorted set
            for _ in range(ADMIT_BATCH_SIZE):
                entries = await redis.zpopmin(key, count=1)
                if not entries:
                    break
                raw_id = entries[0][0]
                if isinstance(raw_id, bytes):
                    user_id = raw_id.decode()
                else:
                    user_id = str(raw_id)

                try:
                    show_uuid = UUID(show_id)
                    user_uuid = UUID(user_id)
                except (ValueError, TypeError):
                    continue

                token = await lock_repo.admit_user(show_uuid, user_uuid)
                logger.info(
                    "user_admitted",
                    show_id=show_id,
                    user_id=user_id,
                    token=token[:8],
                )

        if cursor == 0:
            break
