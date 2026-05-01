"""Integration tests for arq pool in FastAPI lifespan."""

from unittest.mock import AsyncMock, patch

import pytest


class TestArqPoolLifespan:
    """Tests for arq pool initialization in FastAPI lifespan."""

    @pytest.mark.asyncio
    async def test_lifespan_creates_arq_pool_on_app_state(self) -> None:
        """FastAPI lifespan creates app.state.arq_pool when Redis is available."""
        # Import with mocked create_pool
        with patch("stockvaluefinder.main.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            # Also mock other external dependencies
            with (
                patch("stockvaluefinder.main.init_cache") as mock_init_cache,
                patch("stockvaluefinder.main.check_qdrant_health", return_value=True),
            ):
                mock_cache = AsyncMock()
                mock_cache.connect = AsyncMock()
                mock_init_cache.return_value = mock_cache

                # Import app to trigger lifespan
                from stockvaluefinder.main import app

                # Simulate lifespan startup
                async with app.router.lifespan_context(app):
                    # Verify arq_pool was set on app.state
                    assert hasattr(app.state, "arq_pool")
                    assert app.state.arq_pool is mock_pool
                    mock_create_pool.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_graceful_degradation_when_redis_unavailable(self) -> None:
        """FastAPI lifespan sets app.state.arq_pool = None when Redis is unavailable."""
        with patch("stockvaluefinder.main.create_pool") as mock_create_pool:
            mock_create_pool.side_effect = ConnectionError("Redis unavailable")

            with (
                patch("stockvaluefinder.main.init_cache") as mock_init_cache,
                patch("stockvaluefinder.main.check_qdrant_health", return_value=True),
            ):
                mock_cache = AsyncMock()
                mock_cache.connect = AsyncMock()
                mock_init_cache.return_value = mock_cache

                from stockvaluefinder.main import app

                async with app.router.lifespan_context(app):
                    assert hasattr(app.state, "arq_pool")
                    assert app.state.arq_pool is None

    @pytest.mark.asyncio
    async def test_lifespan_closes_arq_pool_on_shutdown(self) -> None:
        """FastAPI lifespan closes arq pool on shutdown."""
        with patch("stockvaluefinder.main.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            with (
                patch("stockvaluefinder.main.init_cache") as mock_init_cache,
                patch("stockvaluefinder.main.check_qdrant_health", return_value=True),
            ):
                mock_cache = AsyncMock()
                mock_cache.connect = AsyncMock()
                mock_cache.disconnect = AsyncMock()
                mock_init_cache.return_value = mock_cache

                from stockvaluefinder.main import app

                async with app.router.lifespan_context(app):
                    pass  # Exit the context to trigger shutdown

                # Verify pool was closed
                mock_pool.close.assert_awaited_once()

    def test_pipeline_router_included_in_app(self) -> None:
        """pipeline_router is imported and included in the app."""
        import inspect

        import stockvaluefinder.main

        source_code = inspect.getsource(stockvaluefinder.main)
        assert "pipeline_router" in source_code
        assert "app.include_router(pipeline_router)" in source_code

    def test_main_imports_create_pool(self) -> None:
        """main.py imports create_pool from arq."""
        import importlib
        import stockvaluefinder.main

        # Force reimport to check imports
        source = importlib.util.find_spec("stockvaluefinder.main")
        assert source is not None

        # Check the module source for create_pool import
        import inspect

        source_code = inspect.getsource(stockvaluefinder.main)
        assert "create_pool" in source_code
        assert "app.state.arq_pool" in source_code
