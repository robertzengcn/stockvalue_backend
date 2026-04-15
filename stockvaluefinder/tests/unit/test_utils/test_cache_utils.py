"""Unit tests for cache wrapper utilities (build_cache_key and cacheable)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from stockvaluefinder.utils.cache import CacheManager, build_cache_key, cacheable
from stockvaluefinder.utils.errors import CacheError


class TestBuildCacheKey:
    """Tests for build_cache_key helper function."""

    def test_simple_key_with_version_and_prefix(self) -> None:
        """build_cache_key should format version:prefix:identifier."""
        key = build_cache_key("v1", "financial_report", "600519.SH")
        assert key == "v1:financial_report:600519.SH"

    def test_key_with_multiple_parts(self) -> None:
        """build_cache_key should join multiple parts with colon."""
        key = build_cache_key("v1", "price", "600519.SH", "2024")
        assert key == "v1:price:600519.SH:2024"

    def test_key_with_no_extra_parts(self) -> None:
        """build_cache_key should work with just version and prefix."""
        key = build_cache_key("v1", "rates")
        assert key == "v1:rates"

    def test_key_with_three_parts(self) -> None:
        """build_cache_key should handle multiple identifier parts."""
        key = build_cache_key("v2", "dividend", "000001.SZ", "2023", "annual")
        assert key == "v2:dividend:000001.SZ:2023:annual"


class TestCacheable:
    """Tests for cacheable async wrapper function."""

    @pytest.mark.asyncio
    async def test_cache_miss_calls_function_and_stores(self) -> None:
        """On cache miss, cacheable should call function and store result."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        cache = CacheManager(redis_url="redis://localhost:6379/0")
        cache._redis = mock_redis
        cache._connected = True

        async def fetch_data(ticker: str) -> dict[str, str | int]:
            return {"ticker": ticker, "revenue": 1000}

        result = await cacheable(
            cache,
            prefix="financial_report",
            ttl=86400,
            version="v1",
            identifier="600519.SH",
            fn=fetch_data,
            ticker="600519.SH",
        )

        # Should return result with cache metadata
        assert result["ticker"] == "600519.SH"
        assert result["revenue"] == 1000
        assert result["_cache"]["hit"] is False
        assert result["_cache"]["cached_at"] is not None

        # Redis.setex should have been called
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_data(self) -> None:
        """On cache hit, cacheable should return cached result with hit=True."""
        cached_data = json.dumps(
            {
                "ticker": "600519.SH",
                "revenue": 1000,
                "_cache": {"hit": False, "cached_at": "2024-01-01T00:00:00+00:00"},
            }
        )
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=cached_data)

        cache = CacheManager(redis_url="redis://localhost:6379/0")
        cache._redis = mock_redis
        cache._connected = True

        call_count = 0

        async def fetch_data(ticker: str) -> dict[str, str | int]:
            nonlocal call_count
            call_count += 1
            return {"ticker": ticker, "revenue": 2000}

        result = await cacheable(
            cache,
            prefix="financial_report",
            ttl=86400,
            version="v1",
            identifier="600519.SH",
            fn=fetch_data,
            ticker="600519.SH",
        )

        # Should return cached result
        assert result["ticker"] == "600519.SH"
        assert result["revenue"] == 1000
        assert result["_cache"]["hit"] is True

        # Function should NOT have been called
        assert call_count == 0

    @pytest.mark.asyncio
    async def test_cache_hit_metadata_preserved(self) -> None:
        """Cache hit should preserve original cached_at timestamp."""
        original_time = "2024-06-15T10:30:00+00:00"
        cached_data = json.dumps(
            {
                "ticker": "600519.SH",
                "_cache": {"hit": False, "cached_at": original_time},
            }
        )
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=cached_data)

        cache = CacheManager(redis_url="redis://localhost:6379/0")
        cache._redis = mock_redis
        cache._connected = True

        async def fetch_data(ticker: str) -> dict[str, str]:
            return {"ticker": ticker}

        result = await cacheable(
            cache,
            prefix="financial_report",
            ttl=86400,
            version="v1",
            identifier="600519.SH",
            fn=fetch_data,
            ticker="600519.SH",
        )

        # cached_at should be the original timestamp, not current time
        assert result["_cache"]["cached_at"] == original_time

    @pytest.mark.asyncio
    async def test_cache_miss_stores_with_correct_key_and_ttl(self) -> None:
        """Cacheable should store result with correct key format and TTL."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        cache = CacheManager(redis_url="redis://localhost:6379/0")
        cache._redis = mock_redis
        cache._connected = True

        async def fetch_data() -> dict[str, str]:
            return {"data": "test"}

        await cacheable(
            cache,
            prefix="price",
            ttl=300,
            version="v1",
            identifier="600519.SH",
            fn=fetch_data,
        )

        # Verify key and TTL in setex call
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "v1:price:600519.SH"
        assert call_args[0][1] == 300

    @pytest.mark.asyncio
    async def test_cacheable_returns_none_fn(self) -> None:
        """Cacheable should handle fn returning None gracefully."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        cache = CacheManager(redis_url="redis://localhost:6379/0")
        cache._redis = mock_redis
        cache._connected = True

        async def fetch_nothing() -> None:
            return None

        result = await cacheable(
            cache,
            prefix="empty",
            ttl=60,
            version="v1",
            identifier="test",
            fn=fetch_nothing,
        )

        # Should still have cache metadata even for None result
        assert result is not None
        assert result["_cache"]["hit"] is False

    @pytest.mark.asyncio
    async def test_cacheable_with_none_cache(self) -> None:
        """Cacheable should call fn directly when cache is None."""

        async def fetch_data(ticker: str) -> dict[str, str | int]:
            return {"ticker": ticker, "revenue": 5000}

        result = await cacheable(
            None,
            prefix="financial_report",
            ttl=86400,
            version="v1",
            identifier="600519.SH",
            fn=fetch_data,
            ticker="600519.SH",
        )

        # Should return raw result without cache metadata
        assert result == {"ticker": "600519.SH", "revenue": 5000}


class TestCacheManagerMethods:
    """Tests for CacheManager connect, disconnect, get, set, delete, exists, clear, delete_by_pattern."""

    @pytest.mark.asyncio
    async def test_connect_success(self) -> None:
        """CacheManager.connect should ping Redis and set _connected=True."""
        cache = CacheManager(redis_url="redis://localhost:6379/0")

        mock_redis_instance = AsyncMock()
        mock_redis_instance.ping = AsyncMock(return_value=True)

        mock_pool = AsyncMock()

        with patch(
            "stockvaluefinder.utils.cache.ConnectionPool.from_url",
            return_value=mock_pool,
        ), patch(
            "stockvaluefinder.utils.cache.Redis",
            return_value=mock_redis_instance,
        ):
            await cache.connect()

        assert cache._connected is True

    @pytest.mark.asyncio
    async def test_disconnect_closes_redis(self) -> None:
        """CacheManager.disconnect should close Redis and set _connected=False."""
        cache = CacheManager(redis_url="redis://localhost:6379/0")
        mock_redis = AsyncMock()
        cache._redis = mock_redis
        cache._connected = True

        await cache.disconnect()

        mock_redis.close.assert_called_once()
        assert cache._connected is False

    @pytest.mark.asyncio
    async def test_get_returns_deserialized_json(self) -> None:
        """CacheManager.get should return deserialized JSON from Redis."""
        cache = CacheManager(redis_url="redis://localhost:6379/0")
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps({"key": "value"}))
        cache._redis = mock_redis
        cache._connected = True

        result = await cache.get("test_key")

        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing_key(self) -> None:
        """CacheManager.get should return None when key is not found."""
        cache = CacheManager(redis_url="redis://localhost:6379/0")
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        cache._redis = mock_redis
        cache._connected = True

        result = await cache.get("missing")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_with_ttl_calls_setex(self) -> None:
        """CacheManager.set with TTL should call redis.setex."""
        cache = CacheManager(redis_url="redis://localhost:6379/0")
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()
        cache._redis = mock_redis
        cache._connected = True

        await cache.set("key", {"data": 1}, ttl=60)

        mock_redis.setex.assert_called_once_with("key", 60, json.dumps({"data": 1}))

    @pytest.mark.asyncio
    async def test_set_without_ttl_calls_set(self) -> None:
        """CacheManager.set without TTL should call redis.set."""
        cache = CacheManager(redis_url="redis://localhost:6379/0")
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        cache._redis = mock_redis
        cache._connected = True

        await cache.set("key", {"data": 1})

        mock_redis.set.assert_called_once_with("key", json.dumps({"data": 1}))

    @pytest.mark.asyncio
    async def test_delete_existing_key(self) -> None:
        """CacheManager.delete should return True when key exists."""
        cache = CacheManager(redis_url="redis://localhost:6379/0")
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=1)
        cache._redis = mock_redis
        cache._connected = True

        result = await cache.delete("key")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self) -> None:
        """CacheManager.delete should return False when key does not exist."""
        cache = CacheManager(redis_url="redis://localhost:6379/0")
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=0)
        cache._redis = mock_redis
        cache._connected = True

        result = await cache.delete("key")

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_returns_true(self) -> None:
        """CacheManager.exists should return True when key exists."""
        cache = CacheManager(redis_url="redis://localhost:6379/0")
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=1)
        cache._redis = mock_redis
        cache._connected = True

        result = await cache.exists("key")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false(self) -> None:
        """CacheManager.exists should return False when key does not exist."""
        cache = CacheManager(redis_url="redis://localhost:6379/0")
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=0)
        cache._redis = mock_redis
        cache._connected = True

        result = await cache.exists("key")

        assert result is False

    @pytest.mark.asyncio
    async def test_clear_calls_flushdb(self) -> None:
        """CacheManager.clear should call redis.flushdb."""
        cache = CacheManager(redis_url="redis://localhost:6379/0")
        mock_redis = AsyncMock()
        mock_redis.flushdb = AsyncMock()
        cache._redis = mock_redis
        cache._connected = True

        await cache.clear()

        mock_redis.flushdb.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_by_pattern_with_matches(self) -> None:
        """CacheManager.delete_by_pattern should return count of deleted keys."""
        cache = CacheManager(redis_url="redis://localhost:6379/0")
        mock_redis = AsyncMock()

        async def mock_scan_iter(match: str = "") -> object:
            """Yield matching keys."""
            for key in ["key1", "key2"]:
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.delete = AsyncMock(return_value=2)
        cache._redis = mock_redis
        cache._connected = True

        result = await cache.delete_by_pattern("test:*")

        assert result == 2

    @pytest.mark.asyncio
    async def test_delete_by_pattern_no_matches(self) -> None:
        """CacheManager.delete_by_pattern should return 0 when no keys match."""
        cache = CacheManager(redis_url="redis://localhost:6379/0")
        mock_redis = AsyncMock()

        async def mock_scan_iter(match: str = "") -> object:
            """Yield nothing."""
            return
            yield  # make this an async generator  # type: ignore[misc]

        mock_redis.scan_iter = mock_scan_iter
        cache._redis = mock_redis
        cache._connected = True

        result = await cache.delete_by_pattern("test:*")

        assert result == 0

    @pytest.mark.asyncio
    async def test_redis_property_raises_when_not_connected(self) -> None:
        """CacheManager.redis should raise CacheError when not connected."""
        cache = CacheManager(redis_url="redis://localhost:6379/0")
        cache._connected = False

        with pytest.raises(CacheError, match="not connected"):
            _ = cache.redis
