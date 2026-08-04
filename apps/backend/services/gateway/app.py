"""FR-11, FR-12, NFR-4, NFR-5, NFR-6: FastAPI application factory."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle — DB engine, Redis pool, background workers."""
    from core.config import settings
    from core.observability import configure_logging, init_sentry

    # NFR-4: Configure structured JSON logging
    configure_logging(
        log_level=settings.LOG_LEVEL,
        log_format=settings.LOG_FORMAT,
    )
    logger.info("app_starting", env=settings.SENTRY_ENVIRONMENT)

    # NFR-5: Initialize Sentry error tracking
    init_sentry(dsn=settings.SENTRY_DSN, environment=settings.SENTRY_ENVIRONMENT)

    # FR-9, NFR-3: Start background workers with supervisor restart
    from services.workers.admitter import run_admitter
    from services.workers.relay import run_relay
    from services.workers.sweeper import run_sweeper

    async def _supervised(name: str, coro_fn):
        """Restart a worker coroutine if it dies unexpectedly."""
        while True:
            try:
                logger.info(f"{name}_worker_starting")
                await coro_fn()
            except asyncio.CancelledError:
                logger.info(f"{name}_worker_cancelled")
                raise
            except Exception as exc:
                logger.error(f"{name}_worker_died", error=str(exc))
                await asyncio.sleep(5)  # back-off before restart

    sweeper_task = asyncio.create_task(_supervised("sweeper", run_sweeper))
    relay_task = asyncio.create_task(_supervised("relay", run_relay))
    admitter_task = asyncio.create_task(_supervised("admitter", run_admitter))

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
    """FR-12, NFR-4: Wire up routers, middleware, and health endpoints."""
    app = FastAPI(
        title="Event Ticketing Backend",
        version="0.1.0",
        lifespan=lifespan,
    )

    # --- Middleware ---
    # Security headers
    from starlette.middleware.base import BaseHTTPMiddleware

    from core.config import settings

    async def _security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), interest-cohort=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' https://js.stripe.com;"
            " style-src 'self' 'unsafe-inline' https://js.stripe.com"
            " https://fonts.googleapis.com;"
            " img-src 'self' data: https://q.stripe.com https://m.stripe.com;"
            " font-src 'self' https://js.stripe.com https://fonts.gstatic.com;"
            " connect-src 'self' https://api.stripe.com;"
            " frame-src 'self' https://js.stripe.com https://hooks.stripe.com;"
            " object-src 'none'"
        )
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    app.add_middleware(BaseHTTPMiddleware, dispatch=_security_headers)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # NFR-4: Request context — binds request_id, trace_id, user_id
    # into structlog contextvars for all downstream log calls.
    # Added FIRST so it runs AFTER IdentityMiddleware (LIFO order).
    from core.middleware import RequestContextMiddleware

    app.add_middleware(RequestContextMiddleware)

    # FR-11: Gateway identity enforcement — JWT validation, header stripping,
    # X-Request-ID + traceparent injection. Must be added AFTER CORS so
    # preflight OPTIONS requests pass through unauthenticated.
    # Added SECOND so it runs BEFORE RequestContextMiddleware (LIFO order).
    from services.gateway.middleware import IdentityMiddleware

    app.add_middleware(IdentityMiddleware)

    # NFR-4: Rate limiting via slowapi
    from fastapi.responses import JSONResponse
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware

    from core.middleware.rate_limit import create_limiter

    limiter = create_limiter()
    app.state.limiter = limiter

    def _rate_limit_handler(request: Request, exc: Exception):
        # NFR-4: Only slowapi's RateLimitExceeded should map to a 429. When the
        # Redis-backed storage is unreachable slowapi can route a ConnectionError
        # here; the stock handler crashes with AttributeError on exc.detail, so
        # degrade to a 503 instead of killing the worker.
        if isinstance(exc, RateLimitExceeded):
            return _rate_limit_exceeded_handler(request, exc)
        logger.warning("rate_limit_backend_unavailable", error=str(exc))
        return JSONResponse(
            status_code=503, content={"detail": "Rate limit backend unavailable"}
        )

    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)  # type: ignore[arg-type]
    # NFR-4: slowapi's middleware looks up handlers by EXACT exception type
    # (app.exception_handlers.get(type(e))). Register the same defensive
    # handler for Redis connection errors so a storage outage never reaches
    # the stock _rate_limit_exceeded_handler (which crashes on exc.detail).
    try:
        from redis.exceptions import ConnectionError as RedisConnectionError

        app.add_exception_handler(RedisConnectionError, _rate_limit_handler)  # type: ignore[arg-type]
    except ImportError:  # pragma: no cover - redis is a hard dependency
        pass
    app.add_middleware(SlowAPIMiddleware)

    # --- Routers ---
    from services.booking.routers.admin import router as admin_router
    from services.booking.routers.booking import router as booking_router
    from services.booking.routers.catalog import router as catalog_router
    from services.booking.routers.queue import router as queue_router
    from services.booking.routers.seats import router as seats_router
    from services.gateway.websocket import ws_router
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
    app.include_router(admin_router)
    app.include_router(ws_router)

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
