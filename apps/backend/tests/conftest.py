from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://testuser:testpass@localhost:5433/event_ticketing"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")
os.environ.setdefault("LOG_FORMAT", "console")
_CERTS_DIR = Path(__file__).resolve().parent.parent / "certs"


@pytest.fixture(scope="session", autouse=True)
def _generate_rsa_keys():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    _CERTS_DIR.mkdir(exist_ok=True)
    private_path = _CERTS_DIR / "private.pem"
    public_path = _CERTS_DIR / "public.pem"
    if private_path.exists() and public_path.exists():
        return
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    private_path.write_bytes(private_bytes)
    public_path.write_bytes(public_bytes)


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    from core.config import settings
    from core.db.base import Base

    try:
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
            conn.execute(text("CREATE SEQUENCE IF NOT EXISTS booking.event_serial_seq START 1"))
            conn.execute(text("CREATE SEQUENCE IF NOT EXISTS booking.movie_serial_seq START 1"))
        yield
        try:
            with sync_engine.begin() as conn:
                Base.metadata.drop_all(bind=conn)
                conn.execute(text("DROP SCHEMA IF EXISTS identity CASCADE"))
                conn.execute(text("DROP SCHEMA IF EXISTS booking CASCADE"))
            sync_engine.dispose()
        except Exception:
            pass
    except Exception:
        yield



@pytest_asyncio.fixture(autouse=True)
async def _dispose_pool():
    yield
    from core.db.session import engine, register_pool_listeners

    try:
        await engine.dispose()
        register_pool_listeners()
    except Exception:
        pass



@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    from core.db.session import async_session_factory

    async with async_session_factory() as session:
        trans = await session.begin()
        yield session
        await trans.rollback()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    from services.gateway.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
