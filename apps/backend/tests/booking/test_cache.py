"""FR-4/NFR-6/NFR-7: CacheRepository unit tests.

Tests the Redis cache operations: get, set, get_or_set (cache-aside),
invalidate, invalidate_pattern, and publish_invalidation.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.booking.repositories.cache_repo import CacheRepository


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.publish = AsyncMock(return_value=1)
    redis.pubsub = MagicMock()
    return redis


@pytest.fixture
def cache_repo(mock_redis: AsyncMock) -> CacheRepository:
    """CacheRepository with mocked Redis."""
    return CacheRepository(redis_client=mock_redis)


@pytest.fixture
def cache_repo_no_redis() -> CacheRepository:
    """CacheRepository with no Redis (simulates Redis down)."""
    return CacheRepository(redis_client=None)


class TestCacheGetSet:
    """FR-4: Basic cache get/set operations."""

    async def test_get_returns_decoded_bytes(
        self, cache_repo: CacheRepository, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get.return_value = b'{"key": "value"}'
        result = await cache_repo.get("test:key")
        assert result == '{"key": "value"}'
        mock_redis.get.assert_called_once_with("test:key")

    async def test_get_returns_none_on_miss(
        self, cache_repo: CacheRepository, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get.return_value = None
        result = await cache_repo.get("miss:key")
        assert result is None

    async def test_get_returns_none_when_redis_is_none(
        self, cache_repo_no_redis: CacheRepository
    ) -> None:
        result = await cache_repo_no_redis.get("test:key")
        assert result is None

    async def test_set_stores_with_ttl(
        self, cache_repo: CacheRepository, mock_redis: AsyncMock
    ) -> None:
        await cache_repo.set("test:key", '{"data": 1}', ttl=60)
        mock_redis.set.assert_called_once_with("test:key", '{"data": 1}', ex=60)

    async def test_set_default_ttl(
        self, cache_repo: CacheRepository, mock_redis: AsyncMock
    ) -> None:
        await cache_repo.set("test:key", "value")
        mock_redis.set.assert_called_once_with("test:key", "value", ex=300)

    async def test_set_noop_when_redis_is_none(
        self, cache_repo_no_redis: CacheRepository
    ) -> None:
        await cache_repo_no_redis.set("test:key", "value")  # Should not raise


class TestCacheInvalidate:
    """FR-4: Cache invalidation operations."""

    async def test_invalidate_deletes_key(
        self, cache_repo: CacheRepository, mock_redis: AsyncMock
    ) -> None:
        await cache_repo.invalidate("old:key")
        mock_redis.delete.assert_called_once_with("old:key")

    async def test_invalidate_noop_when_redis_is_none(
        self, cache_repo_no_redis: CacheRepository
    ) -> None:
        await cache_repo_no_redis.invalidate("old:key")  # Should not raise

    async def test_invalidate_pattern_deletes_matching_keys(
        self, cache_repo: CacheRepository, mock_redis: AsyncMock
    ) -> None:
        async def _fake_scan_iter(*args: object, **kwargs: object) -> object:
            for key in [b"key1", b"key2"]:
                yield key

        mock_redis.scan_iter = _fake_scan_iter
        mock_redis.delete.return_value = 2

        result = await cache_repo.invalidate_pattern("showtime:*")
        assert result == 2
        mock_redis.delete.assert_called_once_with(b"key1", b"key2")

    async def test_invalidate_pattern_returns_zero_on_no_match(
        self, cache_repo: CacheRepository, mock_redis: AsyncMock
    ) -> None:
        async def _empty_scan(*args: object, **kwargs: object) -> object:
            return
            yield  # make it an async generator

        mock_redis.scan_iter = _empty_scan
        result = await cache_repo.invalidate_pattern("nomatch:*")
        assert result == 0

    async def test_invalidate_pattern_returns_zero_on_error(
        self, cache_repo: CacheRepository, mock_redis: AsyncMock
    ) -> None:
        mock_redis.scan_iter = AsyncMock(side_effect=Exception("Redis down"))
        result = await cache_repo.invalidate_pattern("showtime:*")
        assert result == 0

    async def test_invalidate_pattern_returns_zero_when_redis_is_none(
        self, cache_repo_no_redis: CacheRepository
    ) -> None:
        result = await cache_repo_no_redis.invalidate_pattern("showtime:*")
        assert result == 0


class TestCacheAside:
    """FR-4: Cache-aside pattern (get_or_set)."""

    async def test_get_or_set_returns_cached_value(
        self, cache_repo: CacheRepository, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get.return_value = b'["cached_venue_1", "cached_venue_2"]'
        factory = AsyncMock(return_value=["db_venue_1"])

        result = await cache_repo.get_or_set("venues:all", factory)

        assert result == ["cached_venue_1", "cached_venue_2"]
        factory.assert_not_called()
        mock_redis.set.assert_not_called()

    async def test_get_or_set_calls_factory_on_miss(
        self, cache_repo: CacheRepository, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get.return_value = None
        factory = AsyncMock(return_value=["db_venue_1"])

        result = await cache_repo.get_or_set("venues:all", factory, ttl=60)

        assert result == ["db_venue_1"]
        factory.assert_called_once()
        mock_redis.set.assert_called_once_with(
            "venues:all", '["db_venue_1"]', ex=60
        )

    async def test_get_or_set_with_custom_serializers(
        self, cache_repo: CacheRepository, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get.return_value = None
        factory = AsyncMock(return_value={"count": 42})

        def custom_serialize(data: dict) -> str:
            return json.dumps(data)

        def custom_deserialize(data: str) -> dict:
            return json.loads(data)

        result = await cache_repo.get_or_set(
            "count:key",
            factory,
            serialize=custom_serialize,
            deserialize=custom_deserialize,
        )

        assert result == {"count": 42}
        mock_redis.set.assert_called_once()

    async def test_get_or_set_falls_through_on_cache_read_error(
        self, cache_repo: CacheRepository, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get.side_effect = Exception("Redis read error")
        factory = AsyncMock(return_value=["fresh_data"])

        result = await cache_repo.get_or_set("error:key", factory)

        assert result == ["fresh_data"]
        factory.assert_called_once()

    async def test_get_or_set_stores_factory_result_on_write_error(
        self, cache_repo: CacheRepository, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get.return_value = None
        mock_redis.set.side_effect = Exception("Redis write error")
        factory = AsyncMock(return_value=["data"])

        result = await cache_repo.get_or_set("write error:key", factory)

        assert result == ["data"]
        factory.assert_called_once()

    async def test_get_or_set_bypasses_cache_when_redis_is_none(
        self, cache_repo_no_redis: CacheRepository
    ) -> None:
        factory = AsyncMock(return_value=["fresh_data"])

        result = await cache_repo_no_redis.get_or_set("venues:all", factory)

        assert result == ["fresh_data"]
        factory.assert_called_once()


class TestPublishInvalidation:
    """FR-4: Redis Pub/Sub cache invalidation."""

    async def test_publish_invalidation_sends_message(
        self, cache_repo: CacheRepository, mock_redis: AsyncMock
    ) -> None:
        await cache_repo.publish_invalidation(
            "cache:invalidate",
            {"keys": ["seatmap:123"]},
        )
        mock_redis.publish.assert_called_once_with(
            "cache:invalidate", json.dumps({"keys": ["seatmap:123"]})
        )

    async def test_publish_invalidation_noop_when_redis_is_none(
        self, cache_repo_no_redis: CacheRepository
    ) -> None:
        await cache_repo_no_redis.publish_invalidation(
            "cache:invalidate", {"keys": ["test"]}
        )  # Should not raise

    async def test_publish_invalidation_tolerates_error(
        self, cache_repo: CacheRepository, mock_redis: AsyncMock
    ) -> None:
        mock_redis.publish.side_effect = Exception("Redis down")
        await cache_repo.publish_invalidation(
            "cache:invalidate", {"keys": ["test"]}
        )  # Should not raise
