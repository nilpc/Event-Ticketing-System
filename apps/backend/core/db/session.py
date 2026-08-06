from collections.abc import AsyncGenerator
import structlog
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from core.config import settings
logger = structlog.get_logger()

def _on_connect(dbapi_conn, connection_record) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute('SET search_path TO booking,identity,public')
    cursor.close()

def _on_checkout(dbapi_conn, connection_record, connection_proxy) -> None:
    try:
        cursor = dbapi_conn.cursor()
        cursor.execute('SET search_path TO booking,identity,public')
        cursor.close()
    except Exception:
        pass
engine = create_async_engine(settings.DATABASE_URL, pool_size=20, max_overflow=10, pool_pre_ping=True, pool_recycle=300, connect_args={'statement_cache_size': 0})

def register_pool_listeners() -> None:
    event.listen(engine.sync_engine.pool, 'checkout', _on_checkout)
event.listen(engine.sync_engine, 'connect', _on_connect)
register_pool_listeners()
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            if session.in_transaction():
                await session.commit()
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise
