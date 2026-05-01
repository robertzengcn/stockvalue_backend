"""Unit tests for WatcherStateRepository."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from stockvaluefinder.db.models.watcher_state import WatcherStateDB


# ---------------------------------------------------------------------------
# WatcherStateRepository.get_state
# ---------------------------------------------------------------------------


class TestGetState:
    """Tests for WatcherStateRepository.get_state."""

    @pytest.mark.asyncio
    async def test_returns_existing_state(self) -> None:
        """get_state returns existing watcher_state row."""
        from stockvaluefinder.pipeline.watcher_repo import WatcherStateRepository

        existing = WatcherStateDB(
            watcher_id="default",
            last_poll_time=None,
            last_akshare_success=False,
            last_cninfo_fallback=False,
            polls_count=5,
            errors_count=1,
            updated_at=datetime.now(timezone.utc),
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = WatcherStateRepository(mock_session)
        result = await repo.get_state()

        assert result is not None
        assert result.watcher_id == "default"
        assert result.polls_count == 5

    @pytest.mark.asyncio
    async def test_creates_state_if_not_exists(self) -> None:
        """get_state creates a new row if no state exists."""
        from stockvaluefinder.pipeline.watcher_repo import WatcherStateRepository

        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = WatcherStateRepository(mock_session)
        result = await repo.get_state()

        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        assert result.watcher_id == "default"


# ---------------------------------------------------------------------------
# WatcherStateRepository.update_state
# ---------------------------------------------------------------------------


class TestUpdateState:
    """Tests for WatcherStateRepository.update_state."""

    @pytest.mark.asyncio
    async def test_update_state_increments_polls_count(self) -> None:
        """update_state increments polls_count and sets flags."""
        from stockvaluefinder.pipeline.watcher_repo import WatcherStateRepository

        existing = WatcherStateDB(
            watcher_id="default",
            last_poll_time=None,
            last_akshare_success=False,
            last_cninfo_fallback=False,
            polls_count=5,
            errors_count=0,
            updated_at=datetime.now(timezone.utc),
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        repo = WatcherStateRepository(mock_session)
        result = await repo.update_state(
            last_akshare_success=True,
            last_cninfo_fallback=False,
        )

        assert result.polls_count == 6
        assert result.last_akshare_success is True
        assert result.last_cninfo_fallback is False
        assert result.last_poll_time is not None

    @pytest.mark.asyncio
    async def test_update_state_increments_errors_count(self) -> None:
        """update_state increments errors_count when is_error=True."""
        from stockvaluefinder.pipeline.watcher_repo import WatcherStateRepository

        existing = WatcherStateDB(
            watcher_id="default",
            last_poll_time=None,
            last_akshare_success=False,
            last_cninfo_fallback=False,
            polls_count=2,
            errors_count=0,
            updated_at=datetime.now(timezone.utc),
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        repo = WatcherStateRepository(mock_session)
        result = await repo.update_state(
            last_akshare_success=False,
            last_cninfo_fallback=False,
            is_error=True,
        )

        assert result.errors_count == 1
        assert result.polls_count == 3
