"""Tests for admin stock access management routes: GET, POST, DELETE, PUT + RBAC enforcement."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from stockvaluefinder.api.admin_routes import router as admin_router
from stockvaluefinder.api.dependencies import get_current_user
from stockvaluefinder.db.base import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_user(
    user_id: object | None = None,
    email: str = "user@test.com",
    role: str = "user",
    is_active: bool = True,
) -> MagicMock:
    """Build a MagicMock with user attributes matching UserDB fields."""
    user = MagicMock()
    user.id = user_id or uuid4()
    user.email = email
    user.role = role
    user.is_active = is_active
    user.created_at = datetime(2026, 1, 1)
    user.updated_at = datetime(2026, 1, 2)
    return user


def _make_mock_access_entry(
    ticker: str = "600519.SH",
    created_at: datetime | None = None,
) -> MagicMock:
    """Build a MagicMock with UserStockAccessDB fields."""
    entry = MagicMock()
    entry.ticker = ticker
    entry.created_at = created_at or datetime(2026, 5, 10, tzinfo=None)
    return entry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock AsyncSession."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_get_db(mock_db_session: AsyncMock):
    """Override get_db dependency with mock session."""

    async def _override():
        yield mock_db_session

    return _override


@pytest.fixture
def admin_user_id() -> Any:
    """Generate a fixed admin user ID for tests."""
    return uuid4()


@pytest.fixture
def target_user_id() -> Any:
    """Generate a fixed target user ID for tests."""
    return uuid4()


@pytest.fixture
async def app_with_admin(
    mock_get_db: Any,
    admin_user_id: Any,
) -> AsyncGenerator[FastAPI, None]:
    """Create test FastAPI app with admin_router and admin dependency override."""
    app = FastAPI()
    app.include_router(admin_router)

    async def _admin_override() -> dict[str, Any]:
        return {
            "user_id": str(admin_user_id),
            "email": "admin@test.com",
            "role": "admin",
            "is_active": True,
        }

    app.dependency_overrides[get_current_user] = _admin_override
    app.dependency_overrides[get_db] = mock_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def admin_client(app_with_admin: FastAPI):
    """Create async test client with admin privileges."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_admin),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
async def app_with_regular_user(
    mock_get_db: Any,
) -> AsyncGenerator[FastAPI, None]:
    """Create test FastAPI app with regular (non-admin) dependency override."""
    app = FastAPI()
    app.include_router(admin_router)

    async def _regular_override() -> dict[str, Any]:
        return {
            "user_id": str(uuid4()),
            "email": "regular@test.com",
            "role": "user",
            "is_active": True,
        }

    app.dependency_overrides[get_current_user] = _regular_override
    app.dependency_overrides[get_db] = mock_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def regular_client(app_with_regular_user: FastAPI):
    """Create async test client with regular user (non-admin) privileges."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_regular_user),
        base_url="http://test",
    ) as ac:
        yield ac


# ===================================================================
# TestGetStockAccess  (ACCL-02)
# ===================================================================


class TestGetStockAccess:
    """Tests for GET /api/v1/admin/users/{user_id}/stock-access endpoint."""

    @pytest.mark.asyncio
    async def test_get_stock_access_empty_list(
        self,
        admin_client: AsyncClient,
        target_user_id: object,
    ) -> None:
        """ACCL-02: GET returns 200 with empty tickers list for user with no restrictions."""
        with patch(
            "stockvaluefinder.api.admin_routes.UserStockAccessRepository"
        ) as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_all_for_user = AsyncMock(return_value=[])
            MockRepo.return_value = mock_repo

            response = await admin_client.get(
                f"/api/v1/admin/users/{target_user_id}/stock-access"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["user_id"] == str(target_user_id)
            assert data["data"]["tickers"] == []

    @pytest.mark.asyncio
    async def test_get_stock_access_with_entries(
        self,
        admin_client: AsyncClient,
        target_user_id: object,
    ) -> None:
        """ACCL-02: GET returns 200 with tickers list."""
        with patch(
            "stockvaluefinder.api.admin_routes.UserStockAccessRepository"
        ) as MockRepo:
            mock_repo = AsyncMock()
            entry1 = _make_mock_access_entry(ticker="000001.SZ")
            entry2 = _make_mock_access_entry(ticker="600519.SH")
            mock_repo.get_all_for_user = AsyncMock(return_value=[entry1, entry2])
            MockRepo.return_value = mock_repo

            response = await admin_client.get(
                f"/api/v1/admin/users/{target_user_id}/stock-access"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["data"]["tickers"]) == 2
            assert data["data"]["tickers"][0]["ticker"] == "000001.SZ"
            assert data["data"]["tickers"][1]["ticker"] == "600519.SH"


# ===================================================================
# TestAddStockAccess  (ACCL-02)
# ===================================================================


class TestAddStockAccess:
    """Tests for POST /api/v1/admin/users/{user_id}/stock-access endpoint."""

    @pytest.mark.asyncio
    async def test_add_stock_access(
        self,
        admin_client: AsyncClient,
        target_user_id: object,
    ) -> None:
        """ACCL-02: POST adds ticker to user's access list (201)."""
        with (
            patch(
                "stockvaluefinder.api.admin_routes.UserStockAccessRepository"
            ) as MockAccessRepo,
            patch("stockvaluefinder.api.admin_routes.UserRepository") as MockUserRepo,
        ):
            mock_access_repo = AsyncMock()
            mock_access_repo.add_access = AsyncMock(
                return_value=_make_mock_access_entry(ticker="600519.SH")
            )
            entry = _make_mock_access_entry(ticker="600519.SH")
            mock_access_repo.get_all_for_user = AsyncMock(return_value=[entry])
            MockAccessRepo.return_value = mock_access_repo

            mock_user_repo = AsyncMock()
            mock_user_repo.get_by_id = AsyncMock(
                return_value=_make_mock_user(user_id=target_user_id)
            )
            MockUserRepo.return_value = mock_user_repo

            response = await admin_client.post(
                f"/api/v1/admin/users/{target_user_id}/stock-access",
                json={"ticker": "600519.SH"},
            )

            assert response.status_code == 201
            data = response.json()
            assert data["success"] is True
            assert len(data["data"]["tickers"]) == 1
            assert data["data"]["tickers"][0]["ticker"] == "600519.SH"

    @pytest.mark.asyncio
    async def test_add_stock_access_user_not_found(
        self,
        admin_client: AsyncClient,
    ) -> None:
        """ACCL-02: POST with non-existent user_id returns 404."""
        with (
            patch("stockvaluefinder.api.admin_routes.UserStockAccessRepository"),
            patch("stockvaluefinder.api.admin_routes.UserRepository") as MockUserRepo,
        ):
            mock_user_repo = AsyncMock()
            mock_user_repo.get_by_id = AsyncMock(return_value=None)
            MockUserRepo.return_value = mock_user_repo

            response = await admin_client.post(
                f"/api/v1/admin/users/{uuid4()}/stock-access",
                json={"ticker": "600519.SH"},
            )

            assert response.status_code == 404


# ===================================================================
# TestRemoveStockAccess  (ACCL-02)
# ===================================================================


class TestRemoveStockAccess:
    """Tests for DELETE /api/v1/admin/users/{user_id}/stock-access endpoint."""

    @pytest.mark.asyncio
    async def test_remove_stock_access(
        self,
        admin_client: AsyncClient,
        target_user_id: object,
    ) -> None:
        """ACCL-02: DELETE removes ticker from user's access list (200)."""
        with patch(
            "stockvaluefinder.api.admin_routes.UserStockAccessRepository"
        ) as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.remove_access = AsyncMock(return_value=True)
            mock_repo.get_all_for_user = AsyncMock(return_value=[])
            MockRepo.return_value = mock_repo

            response = await admin_client.request(
                "DELETE",
                f"/api/v1/admin/users/{target_user_id}/stock-access",
                json={"ticker": "600519.SH"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_remove_stock_access_not_found(
        self,
        admin_client: AsyncClient,
        target_user_id: object,
    ) -> None:
        """ACCL-02: DELETE with ticker not in list returns 404."""
        with patch(
            "stockvaluefinder.api.admin_routes.UserStockAccessRepository"
        ) as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.remove_access = AsyncMock(return_value=False)
            MockRepo.return_value = mock_repo

            response = await admin_client.request(
                "DELETE",
                f"/api/v1/admin/users/{target_user_id}/stock-access",
                json={"ticker": "600519.SH"},
            )

            assert response.status_code == 404


# ===================================================================
# TestSetStockAccess  (ACCL-02)
# ===================================================================


class TestSetStockAccess:
    """Tests for PUT /api/v1/admin/users/{user_id}/stock-access endpoint."""

    @pytest.mark.asyncio
    async def test_set_stock_access(
        self,
        admin_client: AsyncClient,
        target_user_id: object,
    ) -> None:
        """ACCL-02: PUT replaces entire access list (200)."""
        with (
            patch(
                "stockvaluefinder.api.admin_routes.UserStockAccessRepository"
            ) as MockAccessRepo,
            patch("stockvaluefinder.api.admin_routes.UserRepository") as MockUserRepo,
        ):
            entry1 = _make_mock_access_entry(ticker="000001.SZ")
            entry2 = _make_mock_access_entry(ticker="600519.SH")

            mock_access_repo = AsyncMock()
            mock_access_repo.set_access = AsyncMock(return_value=[entry1, entry2])
            mock_access_repo.get_all_for_user = AsyncMock(return_value=[entry1, entry2])
            MockAccessRepo.return_value = mock_access_repo

            mock_user_repo = AsyncMock()
            mock_user_repo.get_by_id = AsyncMock(
                return_value=_make_mock_user(user_id=target_user_id)
            )
            MockUserRepo.return_value = mock_user_repo

            response = await admin_client.put(
                f"/api/v1/admin/users/{target_user_id}/stock-access",
                json={"tickers": ["600519.SH", "000001.SZ"]},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["data"]["tickers"]) == 2

    @pytest.mark.asyncio
    async def test_set_stock_access_user_not_found(
        self,
        admin_client: AsyncClient,
    ) -> None:
        """ACCL-02: PUT with non-existent user_id returns 404."""
        with (
            patch("stockvaluefinder.api.admin_routes.UserStockAccessRepository"),
            patch("stockvaluefinder.api.admin_routes.UserRepository") as MockUserRepo,
        ):
            mock_user_repo = AsyncMock()
            mock_user_repo.get_by_id = AsyncMock(return_value=None)
            MockUserRepo.return_value = mock_user_repo

            response = await admin_client.put(
                f"/api/v1/admin/users/{uuid4()}/stock-access",
                json={"tickers": ["600519.SH"]},
            )

            assert response.status_code == 404


# ===================================================================
# TestNonAdminRejectedStockAccess  (RBAC-04)
# ===================================================================


class TestNonAdminRejectedStockAccess:
    """Tests verifying non-admin users receive 403 on stock access endpoints."""

    @pytest.mark.asyncio
    async def test_non_admin_get_stock_access_returns_403(
        self,
        regular_client: AsyncClient,
    ) -> None:
        """RBAC-04: Non-admin receives 403 on GET stock access."""
        response = await regular_client.get(
            f"/api/v1/admin/users/{uuid4()}/stock-access"
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_non_admin_add_stock_access_returns_403(
        self,
        regular_client: AsyncClient,
    ) -> None:
        """RBAC-04: Non-admin receives 403 on POST stock access."""
        response = await regular_client.post(
            f"/api/v1/admin/users/{uuid4()}/stock-access",
            json={"ticker": "600519.SH"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_non_admin_remove_stock_access_returns_403(
        self,
        regular_client: AsyncClient,
    ) -> None:
        """RBAC-04: Non-admin receives 403 on DELETE stock access."""
        response = await regular_client.request(
            "DELETE",
            f"/api/v1/admin/users/{uuid4()}/stock-access",
            json={"ticker": "600519.SH"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_non_admin_set_stock_access_returns_403(
        self,
        regular_client: AsyncClient,
    ) -> None:
        """RBAC-04: Non-admin receives 403 on PUT stock access."""
        response = await regular_client.put(
            f"/api/v1/admin/users/{uuid4()}/stock-access",
            json={"tickers": ["600519.SH"]},
        )
        assert response.status_code == 403
