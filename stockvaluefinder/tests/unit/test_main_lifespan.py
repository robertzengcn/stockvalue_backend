"""Unit tests for main.py lifespan cache initialization."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from stockvaluefinder.main import lifespan


class TestLifespanCacheInit:
    """Tests for CacheManager initialization in application lifespan."""

    @pytest.mark.asyncio
    async def test_cache_connect_called_on_startup(self) -> None:
        """CacheManager.connect() should be called during lifespan startup."""
        mock_cache = AsyncMock()
        app = FastAPI()
        app.state = MagicMock()

        with (
            patch(
                "stockvaluefinder.main.CacheManager", return_value=mock_cache
            ) as mock_cm_cls,
            patch("stockvaluefinder.main.settings") as mock_settings,
        ):
            mock_settings.external_data.REDIS_URL = "redis://test:6379/0"

            async with lifespan(app):
                # Verify CacheManager was created with correct URL
                mock_cm_cls.assert_called_once_with(redis_url="redis://test:6379/0")
                # Verify connect was called
                mock_cache.connect.assert_called_once()
                # Verify cache is stored on app.state
                assert app.state.cache is mock_cache

    @pytest.mark.asyncio
    async def test_cache_disconnect_called_on_shutdown(self) -> None:
        """CacheManager.disconnect() should be called during lifespan shutdown."""
        mock_cache = AsyncMock()
        app = FastAPI()
        app.state = MagicMock()

        with (
            patch("stockvaluefinder.main.CacheManager", return_value=mock_cache),
            patch("stockvaluefinder.main.settings") as mock_settings,
        ):
            mock_settings.external_data.REDIS_URL = "redis://test:6379/0"

            async with lifespan(app):
                pass

            # After exiting context, disconnect should have been called
            mock_cache.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_graceful_degradation_when_redis_unavailable(self) -> None:
        """Application should continue without cache if Redis is unavailable."""
        mock_cache = AsyncMock()
        mock_cache.connect.side_effect = Exception("Connection refused")
        app = FastAPI()
        app.state = MagicMock()

        with (
            patch("stockvaluefinder.main.CacheManager", return_value=mock_cache),
            patch("stockvaluefinder.main.settings") as mock_settings,
            patch("stockvaluefinder.main.logger") as mock_logger,
        ):
            mock_settings.external_data.REDIS_URL = "redis://test:6379/0"

            # Should NOT raise - graceful degradation
            async with lifespan(app):
                pass

            # Warning should have been logged
            mock_logger.warning.assert_called()
            # Cache on app.state should be None (graceful degradation)
            assert app.state.cache is None
