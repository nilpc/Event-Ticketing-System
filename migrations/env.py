"""FR-13: Alembic env.py for async SQLAlchemy 2.0 with multi-schema support."""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

from core.db.base import Base  # noqa: E402, F401
from services.booking.models import (  # noqa: E402, F401
    Booking,
    BookingEvent,
    Event,
    OutboxEvent,
    Payment,
    ProcessedWebhookEvent,
    Seat,
    Showtime,
    Venue,
)
from services.identity.models import RefreshToken, User  # noqa: E402, F401

# Alembic Config object
config = context.config

# Override sqlalchemy.url from DATABASE_URL env var
db_url = os.getenv("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

# Logging configuration from .ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Tell Alembic about both schemas
target_metadata.schemas = {"identity", "booking"}


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without a connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table="alembic_version",
        version_table_schema="alembic",
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Run migrations with an established connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table="alembic_version",
        version_table_schema="alembic",
    )
    with context.begin_transaction():
        # Pre-create the alembic schema inside the transaction
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS alembic"))
        connection.execute(text("SET search_path TO booking, identity, public"))
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with an async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
