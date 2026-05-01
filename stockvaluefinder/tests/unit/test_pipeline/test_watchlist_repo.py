"""Unit tests for WatchlistRepository."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from stockvaluefinder.db.models.watchlist import WatchlistDB


# ---------------------------------------------------------------------------
# WatchlistRepository.get_active_tickers
# ---------------------------------------------------------------------------


class TestGetActiveTickers:
    """Tests for WatchlistRepository.get_active_tickers."""

    @pytest.mark.asyncio
    async def test_returns_list_of_active_tickers(self) -> None:
        """get_active_tickers returns list of tickers where is_active=True."""
        from stockvaluefinder.pipeline.watchlist_repo import WatchlistRepository

        mock_session = AsyncMock()
        # scalars().all() returns bare values for column-only select
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            "600519.SH",
            "000001.SZ",
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = WatchlistRepository(mock_session)
        tickers = await repo.get_active_tickers()

        assert tickers == ["600519.SH", "000001.SZ"]

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_active_stocks(self) -> None:
        """get_active_tickers returns empty list when no active stocks."""
        from stockvaluefinder.pipeline.watchlist_repo import WatchlistRepository

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = WatchlistRepository(mock_session)
        tickers = await repo.get_active_tickers()

        assert tickers == []


# ---------------------------------------------------------------------------
# WatchlistRepository.add
# ---------------------------------------------------------------------------


class TestAdd:
    """Tests for WatchlistRepository.add."""

    @pytest.mark.asyncio
    async def test_adds_stock_to_watchlist(self) -> None:
        """add inserts a new stock and returns WatchlistDB."""
        from stockvaluefinder.pipeline.watchlist_repo import WatchlistRepository

        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        repo = WatchlistRepository(mock_session)
        result = await repo.add("600519.SH", "Kweichow Moutai")

        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once()
        assert isinstance(result, WatchlistDB)
        assert result.ticker == "600519.SH"
        assert result.name == "Kweichow Moutai"
        assert result.is_active is True


# ---------------------------------------------------------------------------
# WatchlistRepository.remove
# ---------------------------------------------------------------------------


class TestRemove:
    """Tests for WatchlistRepository.remove."""

    @pytest.mark.asyncio
    async def test_remove_sets_is_active_false(self) -> None:
        """remove sets is_active=False on existing ticker."""
        from stockvaluefinder.pipeline.watchlist_repo import WatchlistRepository

        existing = WatchlistDB(
            ticker="600519.SH",
            name="Kweichow Moutai",
            added_at=datetime.now(timezone.utc),
            is_active=True,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        repo = WatchlistRepository(mock_session)
        result = await repo.remove("600519.SH")

        assert result is not None
        assert result.is_active is False
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_remove_returns_none_when_not_found(self) -> None:
        """remove returns None when ticker not found."""
        from stockvaluefinder.pipeline.watchlist_repo import WatchlistRepository

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = WatchlistRepository(mock_session)
        result = await repo.remove("999999.SH")

        assert result is None


# ---------------------------------------------------------------------------
# WatchlistRepository.get_all
# ---------------------------------------------------------------------------


class TestGetAll:
    """Tests for WatchlistRepository.get_all."""

    @pytest.mark.asyncio
    async def test_get_all_active_only(self) -> None:
        """get_all with active_only=True returns only active stocks."""
        from stockvaluefinder.pipeline.watchlist_repo import WatchlistRepository

        active_stock = WatchlistDB(
            ticker="600519.SH",
            name="Kweichow Moutai",
            added_at=datetime.now(timezone.utc),
            is_active=True,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [active_stock]
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = WatchlistRepository(mock_session)
        result = await repo.get_all(active_only=True)

        assert len(result) == 1
        assert result[0].ticker == "600519.SH"

    @pytest.mark.asyncio
    async def test_get_all_includes_inactive(self) -> None:
        """get_all with active_only=False returns all stocks."""
        from stockvaluefinder.pipeline.watchlist_repo import WatchlistRepository

        active = WatchlistDB(
            ticker="600519.SH",
            name="Moutai",
            added_at=datetime.now(timezone.utc),
            is_active=True,
        )
        inactive = WatchlistDB(
            ticker="000001.SZ",
            name="Ping An",
            added_at=datetime.now(timezone.utc),
            is_active=False,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [active, inactive]
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = WatchlistRepository(mock_session)
        result = await repo.get_all(active_only=False)

        assert len(result) == 2


# ---------------------------------------------------------------------------
# WatchlistRepository.get_by_ticker
# ---------------------------------------------------------------------------


class TestGetByTicker:
    """Tests for WatchlistRepository.get_by_ticker."""

    @pytest.mark.asyncio
    async def test_returns_stock_when_found(self) -> None:
        """get_by_ticker returns WatchlistDB when ticker exists."""
        from stockvaluefinder.pipeline.watchlist_repo import WatchlistRepository

        stock = WatchlistDB(
            ticker="600519.SH",
            name="Kweichow Moutai",
            added_at=datetime.now(timezone.utc),
            is_active=True,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = stock
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = WatchlistRepository(mock_session)
        result = await repo.get_by_ticker("600519.SH")

        assert result is not None
        assert result.ticker == "600519.SH"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        """get_by_ticker returns None when ticker does not exist."""
        from stockvaluefinder.pipeline.watchlist_repo import WatchlistRepository

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = WatchlistRepository(mock_session)
        result = await repo.get_by_ticker("999999.SH")

        assert result is None
