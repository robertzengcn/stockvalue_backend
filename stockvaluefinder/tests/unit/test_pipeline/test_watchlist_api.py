"""Unit tests for watchlist CRUD API endpoints.

Tests POST/GET/DELETE /api/v1/pipeline/watchlist endpoints that
manage the user's stock watchlist for financial report monitoring.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from stockvaluefinder.api.pipeline_routes import router as pipeline_router
from stockvaluefinder.db.base import get_db
from stockvaluefinder.db.models.watchlist import WatchlistDB


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _create_app() -> FastAPI:
    """Create a FastAPI app with the pipeline router for testing.

    Returns:
        FastAPI app with pipeline router registered.
    """
    app = FastAPI()
    app.include_router(pipeline_router)
    return app


def _make_watchlist_db(
    ticker: str = "600519.SH",
    name: str = "Kweichow Moutai",
    is_active: bool = True,
) -> WatchlistDB:
    """Create a WatchlistDB instance for testing.

    Args:
        ticker: Stock ticker.
        name: Stock name.
        is_active: Whether the stock is active.

    Returns:
        WatchlistDB instance with test data.
    """
    return WatchlistDB(
        ticker=ticker,
        name=name,
        added_at=datetime.now(timezone.utc),
        is_active=is_active,
    )


def _mock_db_session() -> AsyncMock:
    """Create a mock AsyncSession for dependency override.

    Returns:
        AsyncMock configured as a database session.
    """
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


# Use the actual function reference for FastAPI dependency overrides
# (mypy requires Callable keys, not string paths)
GET_DB_DEPENDENCY = get_db


def _override_get_db(mock_session: AsyncMock):
    """Create a dependency override for get_db.

    Args:
        mock_session: The mock session to inject.

    Returns:
        Async generator function suitable for FastAPI dependency override.
    """

    async def _get_db_override():
        yield mock_session

    return _get_db_override


# ---------------------------------------------------------------------------
# POST /api/v1/pipeline/watchlist
# ---------------------------------------------------------------------------


class TestPostWatchlist:
    """Tests for POST /api/v1/pipeline/watchlist endpoint."""

    @pytest.mark.asyncio
    async def test_post_valid_ticker_returns_200(self) -> None:
        """Test 1: POST with valid ticker+name returns 200 with ApiResponse[WatchlistItemResponse]."""
        mock_session = _mock_db_session()

        with (
            patch(
                "stockvaluefinder.pipeline.watchlist_repo.WatchlistRepository.add",
                new_callable=AsyncMock,
            ) as mock_add,
            patch(
                "stockvaluefinder.pipeline.watchlist_repo.WatchlistRepository.get_by_ticker",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            mock_add.return_value = _make_watchlist_db()

            app = _create_app()
            app.dependency_overrides[GET_DB_DEPENDENCY] = _override_get_db(mock_session)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/v1/pipeline/watchlist",
                    json={"ticker": "600519.SH", "name": "Kweichow Moutai"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["ticker"] == "600519.SH"
            assert data["data"]["name"] == "Kweichow Moutai"
            assert data["data"]["is_active"] is True

    @pytest.mark.asyncio
    async def test_post_invalid_ticker_returns_422(self) -> None:
        """Test 2: POST with invalid ticker format returns 422 validation error."""
        app = _create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/pipeline/watchlist",
                json={"ticker": "INVALID", "name": "Bad Ticker"},
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_post_duplicate_ticker_returns_400(self) -> None:
        """Test 3: POST with duplicate ticker returns 400 error."""
        mock_session = _mock_db_session()
        existing = _make_watchlist_db()

        with patch(
            "stockvaluefinder.pipeline.watchlist_repo.WatchlistRepository.get_by_ticker",
            new_callable=AsyncMock,
            return_value=existing,
        ):
            app = _create_app()
            app.dependency_overrides[GET_DB_DEPENDENCY] = _override_get_db(mock_session)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/v1/pipeline/watchlist",
                    json={"ticker": "600519.SH", "name": "Kweichow Moutai"},
                )

            assert response.status_code == 400
            data = response.json()
            assert data["success"] is False

    @pytest.mark.asyncio
    async def test_post_empty_name_returns_422(self) -> None:
        """Test 4: POST with empty name returns 422 validation error."""
        app = _create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/pipeline/watchlist",
                json={"ticker": "600519.SH", "name": ""},
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_post_uses_watchlist_repo_add(self) -> None:
        """Test 12: POST endpoint uses WatchlistRepository.add correctly."""
        mock_session = _mock_db_session()

        with (
            patch(
                "stockvaluefinder.pipeline.watchlist_repo.WatchlistRepository.add",
                new_callable=AsyncMock,
            ) as mock_add,
            patch(
                "stockvaluefinder.pipeline.watchlist_repo.WatchlistRepository.get_by_ticker",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            mock_add.return_value = _make_watchlist_db()

            app = _create_app()
            app.dependency_overrides[GET_DB_DEPENDENCY] = _override_get_db(mock_session)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                await client.post(
                    "/api/v1/pipeline/watchlist",
                    json={"ticker": "600519.SH", "name": "Kweichow Moutai"},
                )

            mock_add.assert_awaited_once_with("600519.SH", "Kweichow Moutai")


# ---------------------------------------------------------------------------
# GET /api/v1/pipeline/watchlist
# ---------------------------------------------------------------------------


class TestGetWatchlist:
    """Tests for GET /api/v1/pipeline/watchlist endpoint."""

    @pytest.mark.asyncio
    async def test_get_returns_list_of_items(self) -> None:
        """Test 5: GET returns list of WatchlistItemResponse wrapped in ApiResponse."""
        mock_session = _mock_db_session()
        stocks = [
            _make_watchlist_db("600519.SH", "Kweichow Moutai"),
            _make_watchlist_db("000001.SZ", "Ping An Bank"),
        ]

        with patch(
            "stockvaluefinder.pipeline.watchlist_repo.WatchlistRepository.get_all",
            new_callable=AsyncMock,
            return_value=stocks,
        ):
            app = _create_app()
            app.dependency_overrides[GET_DB_DEPENDENCY] = _override_get_db(mock_session)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/watchlist")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["data"]) == 2
            assert data["data"][0]["ticker"] == "600519.SH"
            assert data["data"][1]["ticker"] == "000001.SZ"

    @pytest.mark.asyncio
    async def test_get_active_only_false_returns_all(self) -> None:
        """Test 6: GET with active_only=false returns all stocks including inactive."""
        mock_session = _mock_db_session()
        stocks = [
            _make_watchlist_db("600519.SH", "Moutai", is_active=True),
            _make_watchlist_db("000001.SZ", "Ping An", is_active=False),
        ]

        with patch(
            "stockvaluefinder.pipeline.watchlist_repo.WatchlistRepository.get_all",
            new_callable=AsyncMock,
            return_value=stocks,
        ) as mock_get_all:
            app = _create_app()
            app.dependency_overrides[GET_DB_DEPENDENCY] = _override_get_db(mock_session)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/api/v1/pipeline/watchlist",
                    params={"active_only": False},
                )

            assert response.status_code == 200
            data = response.json()
            assert len(data["data"]) == 2
            # Verify active_only=False was passed
            mock_get_all.assert_awaited_once_with(active_only=False)

    @pytest.mark.asyncio
    async def test_get_returns_empty_list_when_empty(self) -> None:
        """Test 7: GET returns empty list when watchlist is empty."""
        mock_session = _mock_db_session()

        with patch(
            "stockvaluefinder.pipeline.watchlist_repo.WatchlistRepository.get_all",
            new_callable=AsyncMock,
            return_value=[],
        ):
            app = _create_app()
            app.dependency_overrides[GET_DB_DEPENDENCY] = _override_get_db(mock_session)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/watchlist")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"] == []

    @pytest.mark.asyncio
    async def test_get_uses_watchlist_repo_get_all(self) -> None:
        """Test 13: GET endpoint uses WatchlistRepository.get_all correctly."""
        mock_session = _mock_db_session()

        with patch(
            "stockvaluefinder.pipeline.watchlist_repo.WatchlistRepository.get_all",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_get_all:
            app = _create_app()
            app.dependency_overrides[GET_DB_DEPENDENCY] = _override_get_db(mock_session)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                await client.get("/api/v1/pipeline/watchlist")

            mock_get_all.assert_awaited_once_with(active_only=True)


# ---------------------------------------------------------------------------
# DELETE /api/v1/pipeline/watchlist/{ticker}
# ---------------------------------------------------------------------------


class TestDeleteWatchlist:
    """Tests for DELETE /api/v1/pipeline/watchlist/{ticker} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_returns_200_on_success(self) -> None:
        """Test 8: DELETE returns 200 with success message."""
        mock_session = _mock_db_session()
        removed = _make_watchlist_db(is_active=False)

        with patch(
            "stockvaluefinder.pipeline.watchlist_repo.WatchlistRepository.remove",
            new_callable=AsyncMock,
            return_value=removed,
        ):
            app = _create_app()
            app.dependency_overrides[GET_DB_DEPENDENCY] = _override_get_db(mock_session)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.delete(
                    "/api/v1/pipeline/watchlist/600519.SH",
                )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_delete_returns_404_when_not_found(self) -> None:
        """Test 9: DELETE returns 404 when ticker not in watchlist."""
        mock_session = _mock_db_session()

        with patch(
            "stockvaluefinder.pipeline.watchlist_repo.WatchlistRepository.remove",
            new_callable=AsyncMock,
            return_value=None,
        ):
            app = _create_app()
            app.dependency_overrides[GET_DB_DEPENDENCY] = _override_get_db(mock_session)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.delete(
                    "/api/v1/pipeline/watchlist/999999.SH",
                )

            assert response.status_code == 404
            data = response.json()
            assert data["success"] is False

    @pytest.mark.asyncio
    async def test_delete_invalid_ticker_returns_422(self) -> None:
        """Test 10: DELETE with invalid ticker format returns 422."""
        app = _create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete(
                "/api/v1/pipeline/watchlist/INVALID",
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_delete_uses_watchlist_repo_remove(self) -> None:
        """Test 14: DELETE endpoint uses WatchlistRepository.remove correctly."""
        mock_session = _mock_db_session()
        removed = _make_watchlist_db(is_active=False)

        with patch(
            "stockvaluefinder.pipeline.watchlist_repo.WatchlistRepository.remove",
            new_callable=AsyncMock,
            return_value=removed,
        ) as mock_remove:
            app = _create_app()
            app.dependency_overrides[GET_DB_DEPENDENCY] = _override_get_db(mock_session)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                await client.delete("/api/v1/pipeline/watchlist/600519.SH")

            mock_remove.assert_awaited_once_with("600519.SH")


# ---------------------------------------------------------------------------
# Existing health endpoint regression test
# ---------------------------------------------------------------------------


class TestHealthEndpointRegression:
    """Tests that existing health endpoint still works after adding watchlist endpoints."""

    @pytest.mark.asyncio
    async def test_health_endpoint_still_works(self) -> None:
        """Test 11: Existing GET /api/v1/pipeline/health endpoint still works."""
        mock_pool = AsyncMock()
        mock_pool.ping = AsyncMock(return_value=True)

        app = _create_app()
        app.state.arq_pool = mock_pool

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=None)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_maker = MagicMock(return_value=mock_session)

        with patch(
            "stockvaluefinder.api.pipeline_routes.async_session_maker",
            mock_session_maker,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "status" in data["data"]
