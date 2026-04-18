"""Unit tests for get_cache dependency and cache injection into data_service."""

from unittest.mock import MagicMock, patch

import pytest

from stockvaluefinder.api.dependencies import get_cache, init_cache
from stockvaluefinder.rag.vector_store import QdrantVectorStore
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


class TestCacheInjectionIntoDataService:
    """Tests for cache injection through get_initialized_data_service."""

    @pytest.mark.asyncio
    async def test_cache_injected_into_data_service(self) -> None:
        """get_initialized_data_service should inject cache into service."""
        import stockvaluefinder.api.dependencies as deps
        from stockvaluefinder.external.data_service import ExternalDataService

        # Set up a mock cache
        mock_cache = MagicMock(spec=CacheManager)
        deps._cache_instance = mock_cache

        # Clear the lru_cache to get fresh service
        deps.get_data_service.cache_clear()

        service = None
        async for svc in deps.get_initialized_data_service():
            service = svc

        assert service is not None
        assert isinstance(service, ExternalDataService)
        # Cache should have been injected
        assert service._cache is mock_cache

    @pytest.mark.asyncio
    async def test_no_cache_when_redis_unavailable(self) -> None:
        """Service should work with cache=None when Redis unavailable."""
        import stockvaluefinder.api.dependencies as deps
        from stockvaluefinder.external.data_service import ExternalDataService

        # No cache available
        deps._cache_instance = None
        deps.get_data_service.cache_clear()

        service = None
        async for svc in deps.get_initialized_data_service():
            service = svc

        assert service is not None
        assert isinstance(service, ExternalDataService)
        # Cache should be None (graceful degradation)
        assert service._cache is None


class TestQdrantDependencies:
    """Tests for get_qdrant_client and check_qdrant_health."""

    def test_get_qdrant_client_returns_vector_store(self) -> None:
        """get_qdrant_client should return a QdrantVectorStore instance."""
        import stockvaluefinder.api.dependencies as deps

        # Clear lru_cache to get fresh instance
        deps.get_qdrant_client.cache_clear()

        client = deps.get_qdrant_client()
        assert isinstance(client, QdrantVectorStore)

    def test_get_qdrant_client_is_singleton(self) -> None:
        """get_qdrant_client should return the same instance on repeated calls."""
        import stockvaluefinder.api.dependencies as deps

        deps.get_qdrant_client.cache_clear()

        client1 = deps.get_qdrant_client()
        client2 = deps.get_qdrant_client()
        assert client1 is client2

    def test_check_qdrant_health_returns_true_on_success(self) -> None:
        """check_qdrant_health should return True when Qdrant is reachable."""
        import stockvaluefinder.api.dependencies as deps

        deps.get_qdrant_client.cache_clear()

        with patch.object(deps, "get_qdrant_client") as mock_get_client:
            mock_store = MagicMock(spec=QdrantVectorStore)
            mock_store.ensure_collection_exists.return_value = None
            mock_get_client.return_value = mock_store

            result = deps.check_qdrant_health()

        assert result is True

    def test_check_qdrant_health_returns_false_on_failure(self) -> None:
        """check_qdrant_health should return False when Qdrant is unreachable."""
        import stockvaluefinder.api.dependencies as deps

        with patch.object(
            deps, "get_qdrant_client", side_effect=Exception("Connection refused")
        ):
            result = deps.check_qdrant_health()

        assert result is False
