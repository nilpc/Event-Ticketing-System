"""FR-11, FR-12, NFR-6: FastAPI application factory."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle — DB engine, Redis pool, background workers."""
    logger.info("app_starting", env="development")

    # FR-9, NFR-3: Start background workers
    from services.workers.admitter import run_admitter
    from services.workers.relay import run_relay
    from services.workers.sweeper import run_sweeper

    sweeper_task = asyncio.create_task(run_sweeper())
    relay_task = asyncio.create_task(run_relay())
    admitter_task = asyncio.create_task(run_admitter())

    yield

    # Shutdown background workers
    sweeper_task.cancel()
    relay_task.cancel()
    admitter_task.cancel()

    logger.info("app_shutting_down")
    from core.db.session import engine

    await engine.dispose()

    # Close Redis connection pool on shutdown
    from core.redis import _redis_client

    if _redis_client is not None:
        await _redis_client.aclose()


def create_app() -> FastAPI:
    """FR-12: Wire up routers, middleware, and health endpoints."""
    app = FastAPI(
        title="Event Ticketing Backend",
        version="0.1.0",
        lifespan=lifespan,
    )

    # --- Middleware ---
    from core.config import settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # FR-11: Gateway identity enforcement — JWT validation, header stripping,
    # X-Request-ID + traceparent injection. Must be added AFTER CORS so
    # preflight OPTIONS requests pass through unauthenticated.
    from services.gateway.middleware import IdentityMiddleware

    app.add_middleware(IdentityMiddleware)

    # --- Routers ---
    from services.booking.routers.booking import router as booking_router
    from services.booking.routers.catalog import router as catalog_router
    from services.booking.routers.queue import router as queue_router
    from services.booking.routers.seats import router as seats_router
    from services.identity.routers.auth import router as auth_router
    from services.payment.routers.payment import router as payment_router
    from services.payment.routers.webhooks import router as webhook_router

    app.include_router(auth_router)
    app.include_router(catalog_router)
    app.include_router(payment_router)
    app.include_router(queue_router)
    app.include_router(seats_router)
    app.include_router(booking_router)
    app.include_router(webhook_router)

    # --- Health endpoints (FR-12) ---
    @app.get("/health", tags=["ops"])
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/ready", tags=["ops"])
    async def ready() -> dict:
        # FR-12: ping DB
        try:
            from core.db.session import engine

            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="DB not ready") from exc

        # FR-12: ping Redis
        try:
            from core.redis import get_redis

            r = get_redis()
            await r.ping()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Redis not ready") from exc

        return {"status": "ready"}

    return app
