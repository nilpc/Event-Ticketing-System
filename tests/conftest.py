"""Shared test fixtures — DB session, Redis, TestClient."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure test env vars are set before any app imports
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://testuser:testpass@localhost:5432/event_ticketing",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("LOG_FORMAT", "console")


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    """Create all schemas + tables once per test session.

    Uses a sync SQLAlchemy engine (psycopg2) for setup/teardown so there
    is no event-loop conflict with pytest-asyncio's function-scoped loops.
    """
    from core.config import settings
    from core.db.base import Base
    from services.booking import models as _booking_models  # noqa: F401
    from services.identity import models as _identity_models  # noqa: F401

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "").replace(
        "ssl=require", "sslmode=require"
    )
    sync_engine = create_engine(sync_url)

    with sync_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS identity CASCADE"))
        conn.execute(text("DROP SCHEMA IF EXISTS booking CASCADE"))
        conn.execute(text("CREATE SCHEMA identity"))
        conn.execute(text("CREATE SCHEMA booking"))
        Base.metadata.create_all(bind=conn)

    yield

    with sync_engine.begin() as conn:
        Base.metadata.drop_all(bind=conn)
        conn.execute(text("DROP SCHEMA IF EXISTS identity CASCADE"))
        conn.execute(text("DROP SCHEMA IF EXISTS booking CASCADE"))
    sync_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _dispose_pool():
    """Dispose async engine pool after each test to avoid stale event-loop connections."""
    yield
    from core.db.session import engine, register_pool_listeners

    await engine.dispose()
    register_pool_listeners()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a DB session from the app's session factory."""
    from core.db.session import async_session_factory

    async with async_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wired to the FastAPI app via ASGI transport."""
    from services.gateway.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
