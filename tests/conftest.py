"""Shared test fixtures — DB session, Redis, TestClient."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
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
    """Create all schemas + tables once per test session on the app engine.

    Alembic migrations are not run in tests; we replicate the schema/table
    creation that Alembic would do, using SQLAlchemy's Metadata + raw DDL
    for schema creation (since Meta.create_all does not create schemas).

    Sync fixture using asyncio.run() to avoid event-loop scoping issues
    with pytest-asyncio's function-scoped default loop.
    """
    from core.db.base import Base
    from core.db.session import engine

    async def _create():
        async with engine.begin() as conn:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS identity"))
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS booking"))
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create())
    yield

    async def _drop():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_drop())


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
