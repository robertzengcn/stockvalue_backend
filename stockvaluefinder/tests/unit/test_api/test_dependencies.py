"""Unit tests for get_cache dependency."""

from unittest.mock import MagicMock

import pytest

from stockvaluefinder.api.dependencies import get_cache, init_cache
from stockvaluefinder.utils.cache import CacheManager


class TestGetCacheDependency:
    """Tests for get_cache FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_get_cache_yields_none_when_not_initialized(self) -> None:
        """get_cache should yield None when cache is not initialized."""
        # Reset module state
        import stockvaluefinder.api.dependencies as deps

        deps._cache_instance = None

        result = None
        async for cache in get_cache():
            result = cache

        assert result is None

    @pytest.mark.asyncio
    async def test_get_cache_yields_cache_manager_when_initialized(self) -> None:
        """get_cache should yield CacheManager when initialized."""
        mock_cache = MagicMock(spec=CacheManager)

        # Use init_cache to set the module-level instance
        cache = init_cache("redis://test:6379/0")
        assert isinstance(cache, CacheManager)

        # Replace with mock for verification
        import stockvaluefinder.api.dependencies as deps

        deps._cache_instance = mock_cache

        result = None
        async for cache_val in get_cache():
            result = cache_val

        assert result is mock_cache

    def test_init_cache_creates_cache_manager(self) -> None:
        """init_cache should create and return a CacheManager instance."""
        import stockvaluefinder.api.dependencies as deps

        deps._cache_instance = None

        cache = init_cache("redis://localhost:6379/0")

        assert isinstance(cache, CacheManager)

        # Should also set module-level variable
        assert deps._cache_instance is cache

    def test_init_cache_stores_instance(self) -> None:
        """init_cache should store instance for get_cache to yield."""
        import stockvaluefinder.api.dependencies as deps

        cache = init_cache("redis://localhost:6379/0")

        assert deps._cache_instance is cache
