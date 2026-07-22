"""NFR-4: Rate limiting integration tests.

Tests that the rate limiter is properly configured and returns
429 Too Many Requests when limits are exceeded.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def _low_rate_limits():
    """Override rate limit settings to low values for testing."""
    from core.config.settings import Settings, get_settings

    test_settings = Settings(
        RATE_LIMIT_PUBLIC="5/second",
        RATE_LIMIT_AUTH="3/second",
        RATE_LIMIT_BOOKING="2/second",
    )
    get_settings.cache_clear()
    with patch("core.config.settings", test_settings), \
         patch("core.middleware.rate_limit.settings", test_settings):
        yield


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wired to the FastAPI app via ASGI transport."""
    from httpx import ASGITransport
    from services.gateway.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


class TestRateLimiting:
    """NFR-4: Verify rate limiting is enforced on public endpoints."""

    async def test_catalog_endpoints_accept_normal_traffic(
        self, client: AsyncClient
    ) -> None:
        """Normal traffic should pass through without 429."""
        r = await client.get("/v1/venues")
        assert r.status_code != 429, f"Unexpected rate limit on normal request: {r.status_code}"

    async def test_rate_limit_exceeded_returns_429(self, client: AsyncClient) -> None:
        """Exceeding the rate limit should return 429."""
        # Fire requests rapidly to exceed the 5/second limit
        responses = []
        for _ in range(10):
            r = await client.get("/v1/venues")
            responses.append(r.status_code)

        assert 429 in responses, (
            f"Expected 429 in responses, got: {responses}"
        )

    async def test_rate_limit_headers_present(self, client: AsyncClient) -> None:
        """Rate-limited responses should include Retry-After header."""
        # Exhaust the limit
        for _ in range(6):
            r = await client.get("/v1/venues")

        if r.status_code == 429:
            assert "retry-after" in r.headers or "Retry-After" in r.headers


class TestRateLimitConfig:
    """NFR-4: Verify rate limiter configuration."""

    def test_limiter_creation(self) -> None:
        """Rate limiter can be created with settings."""
        from core.middleware.rate_limit import create_limiter

        limiter = create_limiter()
        assert limiter is not None
        assert limiter._default_limits is not None
