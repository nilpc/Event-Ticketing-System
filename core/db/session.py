"""NFR-6, FR-13: Async SQLAlchemy engine and session factory."""

from collections.abc import AsyncGenerator

import structlog
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import settings

logger = structlog.get_logger()


def _on_connect(dbapi_conn, connection_record) -> None:
    """FR-10: Set search_path so asyncpg resolves booking schema enums."""
    cursor = dbapi_conn.cursor()
    cursor.execute("SET search_path TO booking,identity,public")
    cursor.close()


def _on_checkout(dbapi_conn, connection_record, connection_proxy) -> None:
    """FR-10: Re-set search_path on every checkout (safe against pool recycling)."""
    cursor = dbapi_conn.cursor()
    cursor.execute("SET search_path TO booking,identity,public")
    cursor.close()


engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300,  # Recycle connections every 5 min (Neon idle timeout)
    # PgBouncer compat: disable asyncpg prepared-statement cache
    connect_args={"statement_cache_size": 0},
)


def register_pool_listeners() -> None:
    """FR-10: Register listeners on current pool. Call after engine.dispose()."""
    event.listen(engine.sync_engine.pool, "checkout", _on_checkout)


# FR-10: Ensure every connection has the correct search_path.
event.listen(engine.sync_engine, "connect", _on_connect)
register_pool_listeners()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an AsyncSession, commits on success, rolls back on error."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
