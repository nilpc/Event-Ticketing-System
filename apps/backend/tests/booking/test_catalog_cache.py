"""FR-4: Catalog cache-aside integration tests.

Tests that CatalogService properly uses CacheRepository for
caching catalog data with the cache-aside pattern.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from services.booking.repositories.cache_repo import CacheRepository
from services.booking.schemas.catalog import VenueResponse
from services.booking.services.catalog_service import CatalogService


@pytest.fixture
def mock_session() -> AsyncMock:
    """Mock SQLAlchemy session."""
    return AsyncMock()


@pytest.fixture
def mock_cache_repo() -> AsyncMock:
    """Mock CacheRepository."""
    cache = AsyncMock(spec=CacheRepository)
    cache.get_or_set = AsyncMock()
    cache.invalidate = AsyncMock()
    cache.publish_invalidation = AsyncMock()
    return cache


@pytest.fixture
def catalog_service(mock_session: AsyncMock, mock_cache_repo: AsyncMock) -> CatalogService:
    """CatalogService with mocked dependencies."""
    return CatalogService(mock_session, mock_cache_repo)


class TestCatalogCacheAside:
    """FR-4: Verify cache-aside pattern in CatalogService."""

    async def test_list_venues_uses_cache(
        self, catalog_service: CatalogService, mock_cache_repo: AsyncMock
    ) -> None:
        """list_venues should call cache.get_or_set with correct key."""
        mock_cache_repo.get_or_set.return_value = [
            {"venue_id": str(uuid4()), "name": "Test Venue", "capacity": 100}
        ]

        result = await catalog_service.list_venues()

        mock_cache_repo.get_or_set.assert_called_once()
        call_args = mock_cache_repo.get_or_set.call_args
        assert call_args[0][0] == "venues:all"
        assert len(result) == 1
        assert isinstance(result[0], VenueResponse)

    async def test_list_events_uses_cache(
        self, catalog_service: CatalogService, mock_cache_repo: AsyncMock
    ) -> None:
        """list_events should call cache.get_or_set with correct key."""
        mock_cache_repo.get_or_set.return_value = [
            {
                "event_id": f"STE{uuid4().hex[:6].upper()}",
                "event_type": "EVENT",
                "name": "Test Event",
            }
        ]

        await catalog_service.list_events()

        mock_cache_repo.get_or_set.assert_called_once()
        call_args = mock_cache_repo.get_or_set.call_args
        assert call_args[0][0] == "events:all"

    async def test_invalidate_seat_map_calls_cache_and_publishes(
        self, catalog_service: CatalogService, mock_cache_repo: AsyncMock
    ) -> None:
        """invalidate_seat_map should invalidate cache and publish event."""
        show_id = uuid4()

        await catalog_service.invalidate_seat_map(show_id)

        mock_cache_repo.invalidate.assert_called_once_with(f"seatmap:{show_id}")
        mock_cache_repo.publish_invalidation.assert_called_once()

    async def test_invalidate_seat_map_tolerates_cache_error(
        self, catalog_service: CatalogService, mock_cache_repo: AsyncMock
    ) -> None:
        """invalidate_seat_map should not raise on cache errors."""
        mock_cache_repo.invalidate.side_effect = Exception("Redis down")

        show_id = uuid4()
        await catalog_service.invalidate_seat_map(show_id)  # Should not raise

    async def test_invalidate_seat_map_tolerates_publish_error(
        self, catalog_service: CatalogService, mock_cache_repo: AsyncMock
    ) -> None:
        """invalidate_seat_map should not raise on publish errors."""
        mock_cache_repo.publish_invalidation.side_effect = Exception("Redis down")

        show_id = uuid4()
        await catalog_service.invalidate_seat_map(show_id)  # Should not raise
