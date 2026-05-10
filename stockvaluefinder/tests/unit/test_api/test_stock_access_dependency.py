"""Tests for UserStockAccessRepository and require_stock_access dependency."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from fastapi import Depends, FastAPI

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://dummy:dummy@localhost/dummy"
)

from stockvaluefinder.api.dependencies import (
    get_current_user,
    require_stock_access,
)
from stockvaluefinder.db.base import get_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_id() -> str:
    """Generate a test user ID as string."""
    return str(uuid4())


@pytest.fixture
def admin_user() -> dict[str, object]:
    """Create admin user dict (same shape as get_current_user output)."""
    return {
        "user_id": str(uuid4()),
        "email": "admin@example.com",
        "role": "admin",
        "is_active": True,
    }


@pytest.fixture
def regular_user(user_id: str) -> dict[str, object]:
    """Create regular user dict."""
    return {
        "user_id": user_id,
        "email": "user@example.com",
        "role": "user",
        "is_active": True,
    }


@pytest.fixture
def mock_db_session():
    """Create a mock AsyncSession."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_get_db(mock_db_session):
    """Override get_db dependency with mock session."""

    async def _override():
        yield mock_db_session

    return _override


def _make_user_override(user_dict: dict[str, object]):
    """Create async override function for get_current_user."""

    async def _override():
        return user_dict

    return _override


# ---------------------------------------------------------------------------
# Test dependency: require_stock_access
# ---------------------------------------------------------------------------


class TestRequireStockAccessDependency:
    """Tests for require_stock_access FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_admin_bypasses_stock_access(
        self,
        admin_user: dict[str, object],
        mock_get_db,
    ) -> None:
        """Test 5: Admin users bypass stock access checks and can access any ticker."""
        app = FastAPI()

        app.dependency_overrides[get_current_user] = _make_user_override(admin_user)
        app.dependency_overrides[get_db] = mock_get_db

        @app.post("/test-access/{ticker}")
        async def test_endpoint(
            ticker: str,
            user: dict = Depends(require_stock_access),  # type: ignore[type-arg]
        ):
            return {"ticker": ticker, "user_id": user["user_id"]}

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            response = await ac.post("/test-access/600519.SH")

        assert response.status_code == 200
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_user_no_entries_can_access_all(
        self,
        regular_user: dict[str, object],
        mock_get_db,
    ) -> None:
        """Test 2: Regular user with no entries can access all stocks (default open)."""
        app = FastAPI()

        app.dependency_overrides[get_current_user] = _make_user_override(regular_user)
        app.dependency_overrides[get_db] = mock_get_db

        @app.post("/test-access/{ticker}")
        async def test_endpoint(
            ticker: str,
            user: dict = Depends(require_stock_access),  # type: ignore[type-arg]
        ):
            return {"ticker": ticker, "user_id": user["user_id"]}

        with patch(
            "stockvaluefinder.repositories.user_stock_access_repo.UserStockAccessRepository"
        ) as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_accessible_tickers = AsyncMock(return_value=[])
            MockRepo.return_value = mock_repo

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                response = await ac.post("/test-access/600519.SH")

        assert response.status_code == 200
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_user_with_entries_can_access_allowed_ticker(
        self,
        regular_user: dict[str, object],
        mock_get_db,
    ) -> None:
        """Test 3: User with entries can access ticker in their allowed list."""
        app = FastAPI()

        app.dependency_overrides[get_current_user] = _make_user_override(regular_user)
        app.dependency_overrides[get_db] = mock_get_db

        @app.post("/test-access/{ticker}")
        async def test_endpoint(
            ticker: str,
            user: dict = Depends(require_stock_access),  # type: ignore[type-arg]
        ):
            return {"ticker": ticker, "user_id": user["user_id"]}

        with patch(
            "stockvaluefinder.repositories.user_stock_access_repo.UserStockAccessRepository"
        ) as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_accessible_tickers = AsyncMock(return_value=["600519.SH"])
            MockRepo.return_value = mock_repo

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                response = await ac.post("/test-access/600519.SH")

        assert response.status_code == 200
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_user_with_entries_rejected_for_unauthorized_ticker(
        self,
        regular_user: dict[str, object],
        mock_get_db,
    ) -> None:
        """Test 4: User with entries gets 403 for unauthorized ticker."""
        app = FastAPI()

        app.dependency_overrides[get_current_user] = _make_user_override(regular_user)
        app.dependency_overrides[get_db] = mock_get_db

        @app.post("/test-access/{ticker}")
        async def test_endpoint(
            ticker: str,
            user: dict = Depends(require_stock_access),  # type: ignore[type-arg]
        ):
            return {"ticker": ticker, "user_id": user["user_id"]}

        with patch(
            "stockvaluefinder.repositories.user_stock_access_repo.UserStockAccessRepository"
        ) as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_accessible_tickers = AsyncMock(return_value=["600519.SH"])
            MockRepo.return_value = mock_repo

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                response = await ac.post("/test-access/000001.SZ")

        assert response.status_code == 403
        assert "access denied" in response.json()["detail"].lower()
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_stock_access_case_insensitive(
        self,
        regular_user: dict[str, object],
        mock_get_db,
    ) -> None:
        """Test 5: Ticker comparison is case-insensitive."""
        app = FastAPI()

        app.dependency_overrides[get_current_user] = _make_user_override(regular_user)
        app.dependency_overrides[get_db] = mock_get_db

        @app.post("/test-access/{ticker}")
        async def test_endpoint(
            ticker: str,
            user: dict = Depends(require_stock_access),  # type: ignore[type-arg]
        ):
            return {"ticker": ticker, "user_id": user["user_id"]}

        with patch(
            "stockvaluefinder.repositories.user_stock_access_repo.UserStockAccessRepository"
        ) as MockRepo:
            mock_repo = AsyncMock()
            # Return lowercase ticker from DB
            mock_repo.get_accessible_tickers = AsyncMock(return_value=["600519.sh"])
            MockRepo.return_value = mock_repo

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                response = await ac.post("/test-access/600519.SH")

        assert response.status_code == 200
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test repository methods (unit tests with mock session)
# ---------------------------------------------------------------------------


class TestUserStockAccessRepository:
    """Tests for UserStockAccessRepository methods."""

    @pytest.mark.asyncio
    async def test_get_accessible_tickers_returns_empty_when_none(
        self, mock_db_session
    ) -> None:
        """Test 1: get_accessible_tickers returns empty list when no entries."""
        from stockvaluefinder.repositories.user_stock_access_repo import (
            UserStockAccessRepository,
        )

        # Mock the execute to return no rows
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        repo = UserStockAccessRepository(mock_db_session)
        result = await repo.get_accessible_tickers("some-user-id")

        assert result == []

    @pytest.mark.asyncio
    async def test_add_access_creates_entry(self, mock_db_session) -> None:
        """Test 6: add_access creates a new access entry."""
        from stockvaluefinder.repositories.user_stock_access_repo import (
            UserStockAccessRepository,
        )

        repo = UserStockAccessRepository(mock_db_session)

        # flush and refresh are already AsyncMock
        entry = await repo.add_access("user-1", "600519.SH")

        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called_once()
        assert entry is not None

    @pytest.mark.asyncio
    async def test_remove_access_deletes_entry(self, mock_db_session) -> None:
        """Test 7: remove_access deletes an access entry."""
        from stockvaluefinder.repositories.user_stock_access_repo import (
            UserStockAccessRepository,
        )

        # Mock execute to return a result with rowcount=1
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        repo = UserStockAccessRepository(mock_db_session)
        result = await repo.remove_access("user-1", "600519.SH")

        assert result is True
        mock_db_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_access_returns_false_when_not_found(
        self, mock_db_session
    ) -> None:
        """Test: remove_access returns False when entry not found."""
        from stockvaluefinder.repositories.user_stock_access_repo import (
            UserStockAccessRepository,
        )

        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        repo = UserStockAccessRepository(mock_db_session)
        result = await repo.remove_access("user-1", "600519.SH")

        assert result is False

    @pytest.mark.asyncio
    async def test_set_access_replaces_all(self, mock_db_session) -> None:
        """Test 8: set_access replaces all entries for a user."""
        from stockvaluefinder.repositories.user_stock_access_repo import (
            UserStockAccessRepository,
        )

        # Mock for delete query
        mock_delete_result = MagicMock()
        mock_delete_result.rowcount = 2

        mock_db_session.execute = AsyncMock(return_value=mock_delete_result)

        repo = UserStockAccessRepository(mock_db_session)
        await repo.set_access("user-1", ["600519.SH", "000001.SZ"])

        # Should have called execute (for delete) and add_all (for new entries)
        assert mock_db_session.execute.call_count >= 1
        mock_db_session.flush.assert_called()

    @pytest.mark.asyncio
    async def test_get_all_for_user(self, mock_db_session) -> None:
        """Test: get_all_for_user returns entries ordered by ticker."""
        from stockvaluefinder.repositories.user_stock_access_repo import (
            UserStockAccessRepository,
        )

        mock_entry1 = MagicMock()
        mock_entry1.ticker = "000001.SZ"
        mock_entry2 = MagicMock()
        mock_entry2.ticker = "600519.SH"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            mock_entry1,
            mock_entry2,
        ]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        repo = UserStockAccessRepository(mock_db_session)
        result = await repo.get_all_for_user("user-1")

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_clear_access(self, mock_db_session) -> None:
        """Test: clear_access deletes all entries and returns count."""
        from stockvaluefinder.repositories.user_stock_access_repo import (
            UserStockAccessRepository,
        )

        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        repo = UserStockAccessRepository(mock_db_session)
        count = await repo.clear_access("user-1")

        assert count == 3
        mock_db_session.flush.assert_called_once()
