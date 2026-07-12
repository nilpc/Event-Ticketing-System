"""FR-12, NFR-6: FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle — DB engine, Redis pool."""
    logger.info("app_starting", env="development")
    yield
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Routers ---
    from services.booking.routers.catalog import router as catalog_router
    from services.identity.routers.auth import router as auth_router
    from services.payment.routers.payment import router as payment_router

    app.include_router(auth_router)
    app.include_router(catalog_router)
    app.include_router(payment_router)

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
