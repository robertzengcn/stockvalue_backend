"""Unit tests for main.py lifespan cache and Qdrant initialization."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from stockvaluefinder.main import lifespan


def _make_app() -> FastAPI:
    """Create a FastAPI app with mocked state for lifespan tests."""
    app = FastAPI()
    app.state = MagicMock()
    return app


class TestLifespanCacheInit:
    """Tests for CacheManager initialization in application lifespan."""

    @pytest.mark.asyncio
    async def test_cache_connect_called_on_startup(self) -> None:
        """CacheManager.connect() should be called during lifespan startup."""
        mock_cache = AsyncMock()
        app = _make_app()

        with (
            patch(
                "stockvaluefinder.main.init_cache", return_value=mock_cache
            ) as mock_init,
            patch("stockvaluefinder.main.settings") as mock_settings,
            patch("stockvaluefinder.main.check_qdrant_health", return_value=True),
        ):
            mock_settings.external_data.REDIS_URL = "redis://test:6379/0"

            async with lifespan(app):
                # Verify init_cache was called with correct URL
                mock_init.assert_called_once_with(redis_url="redis://test:6379/0")
                # Verify connect was called
                mock_cache.connect.assert_called_once()
                # Verify cache is stored on app.state
                assert app.state.cache is mock_cache

    @pytest.mark.asyncio
    async def test_cache_disconnect_called_on_shutdown(self) -> None:
        """CacheManager.disconnect() should be called during lifespan shutdown."""
        mock_cache = AsyncMock()
        app = _make_app()

        with (
            patch("stockvaluefinder.main.init_cache", return_value=mock_cache),
            patch("stockvaluefinder.main.settings") as mock_settings,
            patch("stockvaluefinder.main.check_qdrant_health", return_value=True),
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
        app = _make_app()

        with (
            patch("stockvaluefinder.main.init_cache", return_value=mock_cache),
            patch("stockvaluefinder.main.settings") as mock_settings,
            patch("stockvaluefinder.main.logger") as mock_logger,
            patch("stockvaluefinder.main.check_qdrant_health", return_value=True),
        ):
            mock_settings.external_data.REDIS_URL = "redis://test:6379/0"

            # Should NOT raise - graceful degradation
            async with lifespan(app):
                pass

            # Warning should have been logged
            mock_logger.warning.assert_called()
            # Cache on app.state should be None (graceful degradation)
            assert app.state.cache is None


class TestLifespanQdrantHealthCheck:
    """Tests for Qdrant health check in application lifespan."""

    @pytest.mark.asyncio
    async def test_qdrant_health_check_called_on_startup(self) -> None:
        """check_qdrant_health should be called during lifespan startup."""
        mock_cache = AsyncMock()
        app = _make_app()

        with (
            patch("stockvaluefinder.main.init_cache", return_value=mock_cache),
            patch("stockvaluefinder.main.settings") as mock_settings,
            patch("stockvaluefinder.main.check_qdrant_health") as mock_health,
        ):
            mock_settings.external_data.REDIS_URL = "redis://test:6379/0"
            mock_health.return_value = True

            async with lifespan(app):
                pass

            mock_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_qdrant_unavailable_does_not_crash_app(self) -> None:
        """Application should start even if Qdrant health check fails."""
        mock_cache = AsyncMock()
        app = _make_app()

        with (
            patch("stockvaluefinder.main.init_cache", return_value=mock_cache),
            patch("stockvaluefinder.main.settings") as mock_settings,
            patch("stockvaluefinder.main.check_qdrant_health") as mock_health,
            patch("stockvaluefinder.main.logger") as mock_logger,
        ):
            mock_settings.external_data.REDIS_URL = "redis://test:6379/0"
            mock_health.return_value = False

            # Should NOT raise - graceful degradation
            async with lifespan(app):
                pass

            # Warning should have been logged about Qdrant
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_qdrant_health_exception_does_not_crash_app(self) -> None:
        """Application should start even if Qdrant health check throws."""
        mock_cache = AsyncMock()
        app = _make_app()

        with (
            patch("stockvaluefinder.main.init_cache", return_value=mock_cache),
            patch("stockvaluefinder.main.settings") as mock_settings,
            patch(
                "stockvaluefinder.main.check_qdrant_health",
                side_effect=Exception("Unexpected error"),
            ),
            patch("stockvaluefinder.main.logger") as mock_logger,
        ):
            mock_settings.external_data.REDIS_URL = "redis://test:6379/0"

            # Should NOT raise - graceful degradation
            async with lifespan(app):
                pass

            mock_logger.warning.assert_called()
