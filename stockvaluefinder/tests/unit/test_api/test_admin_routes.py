"""Tests for admin management routes: list, get, status, role, delete + RBAC enforcement."""

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
    deleted_at: datetime | None = None,
) -> MagicMock:
    """Build a MagicMock with user attributes matching UserDB fields."""
    user = MagicMock()
    user.id = user_id or uuid4()
    user.email = email
    user.role = role
    user.is_active = is_active
    user.created_at = datetime(2026, 1, 1)
    user.updated_at = datetime(2026, 1, 2)
    user.deleted_at = deleted_at
    return user


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
    """Generate a fixed target (non-admin) user ID for tests."""
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
# TestAdminListUsers  (ADMN-01)
# ===================================================================


class TestAdminListUsers:
    """Tests for GET /api/v1/admin/users endpoint."""

    @pytest.mark.asyncio
    async def test_list_users_returns_paginated_response(
        self,
        admin_client: AsyncClient,
        target_user_id: object,
    ) -> None:
        """ADMN-01: Admin can list users and receives paginated response."""
        with patch("stockvaluefinder.api.admin_routes.UserRepository") as MockRepo:
            mock_repo = AsyncMock()
            user1 = _make_mock_user(user_id=uuid4(), email="a@test.com")
            user2 = _make_mock_user(user_id=uuid4(), email="b@test.com")
            mock_repo.list_users = AsyncMock(return_value=([user1, user2], 2))
            MockRepo.return_value = mock_repo

            response = await admin_client.get("/api/v1/admin/users")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["data"]["users"]) == 2
            assert data["data"]["pagination"]["total"] == 2
            assert data["data"]["pagination"]["page"] == 1
            assert data["data"]["pagination"]["limit"] == 20

    @pytest.mark.asyncio
    async def test_list_users_default_pagination(
        self,
        admin_client: AsyncClient,
    ) -> None:
        """ADMN-01: Default pagination is page=1, limit=20."""
        with patch("stockvaluefinder.api.admin_routes.UserRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.list_users = AsyncMock(return_value=([], 0))
            MockRepo.return_value = mock_repo

            await admin_client.get("/api/v1/admin/users")

            mock_repo.list_users.assert_called_once_with(page=1, limit=20)

    @pytest.mark.asyncio
    async def test_list_users_custom_pagination(
        self,
        admin_client: AsyncClient,
    ) -> None:
        """ADMN-01: Custom pagination params are forwarded to repository."""
        with patch("stockvaluefinder.api.admin_routes.UserRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.list_users = AsyncMock(return_value=([], 0))
            MockRepo.return_value = mock_repo

            await admin_client.get("/api/v1/admin/users?page=2&limit=10")

            mock_repo.list_users.assert_called_once_with(page=2, limit=10)

    @pytest.mark.asyncio
    async def test_list_users_empty(
        self,
        admin_client: AsyncClient,
    ) -> None:
        """ADMN-01: Empty user list returns success with empty users array."""
        with patch("stockvaluefinder.api.admin_routes.UserRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.list_users = AsyncMock(return_value=([], 0))
            MockRepo.return_value = mock_repo

            response = await admin_client.get("/api/v1/admin/users")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["users"] == []
            assert data["data"]["pagination"]["total"] == 0


# ===================================================================
# TestAdminGetUser  (ADMN-02)
# ===================================================================


class TestAdminGetUser:
    """Tests for GET /api/v1/admin/users/{user_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_user_returns_details(
        self,
        admin_client: AsyncClient,
        target_user_id: object,
    ) -> None:
        """ADMN-02: Admin can get a single user's details by ID."""
        with patch("stockvaluefinder.api.admin_routes.UserRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_user = _make_mock_user(
                user_id=target_user_id,
                email="target@test.com",
            )
            mock_repo.get_by_id = AsyncMock(return_value=mock_user)
            MockRepo.return_value = mock_repo

            response = await admin_client.get(f"/api/v1/admin/users/{target_user_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["id"] == str(target_user_id)
            assert data["data"]["email"] == "target@test.com"
            assert data["data"]["role"] == "user"
            assert data["data"]["is_active"] is True
            assert "created_at" in data["data"]
            assert "updated_at" in data["data"]
            assert "deleted_at" in data["data"]

    @pytest.mark.asyncio
    async def test_get_user_not_found(
        self,
        admin_client: AsyncClient,
    ) -> None:
        """ADMN-02: Non-existent user returns 404."""
        with patch("stockvaluefinder.api.admin_routes.UserRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_by_id = AsyncMock(return_value=None)
            MockRepo.return_value = mock_repo

            response = await admin_client.get(f"/api/v1/admin/users/{uuid4()}")

            assert response.status_code == 404


# ===================================================================
# TestAdminUpdateStatus  (ADMN-03)
# ===================================================================


class TestAdminUpdateStatus:
    """Tests for PATCH /api/v1/admin/users/{user_id}/status endpoint."""

    @pytest.mark.asyncio
    async def test_disable_user(
        self,
        admin_client: AsyncClient,
        target_user_id: object,
    ) -> None:
        """ADMN-03: Admin can disable a user account."""
        with patch("stockvaluefinder.api.admin_routes.UserRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_user = _make_mock_user(
                user_id=target_user_id,
                is_active=False,
            )
            mock_repo.set_active = AsyncMock(return_value=mock_user)
            MockRepo.return_value = mock_repo

            response = await admin_client.patch(
                f"/api/v1/admin/users/{target_user_id}/status",
                json={"is_active": False},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["is_active"] is False

    @pytest.mark.asyncio
    async def test_enable_user(
        self,
        admin_client: AsyncClient,
        target_user_id: object,
    ) -> None:
        """ADMN-03: Admin can enable a user account."""
        with patch("stockvaluefinder.api.admin_routes.UserRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_user = _make_mock_user(
                user_id=target_user_id,
                is_active=True,
            )
            mock_repo.set_active = AsyncMock(return_value=mock_user)
            MockRepo.return_value = mock_repo

            response = await admin_client.patch(
                f"/api/v1/admin/users/{target_user_id}/status",
                json={"is_active": True},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["is_active"] is True

    @pytest.mark.asyncio
    async def test_update_status_user_not_found(
        self,
        admin_client: AsyncClient,
    ) -> None:
        """ADMN-03: Updating status for non-existent user returns 404."""
        with patch("stockvaluefinder.api.admin_routes.UserRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.set_active = AsyncMock(return_value=None)
            MockRepo.return_value = mock_repo

            response = await admin_client.patch(
                f"/api/v1/admin/users/{uuid4()}/status",
                json={"is_active": False},
            )

            assert response.status_code == 404


# ===================================================================
# TestAdminUpdateRole  (ADMN-05, RBAC-03)
# ===================================================================


class TestAdminUpdateRole:
    """Tests for PATCH /api/v1/admin/users/{user_id}/role endpoint."""

    @pytest.mark.asyncio
    async def test_promote_user_to_admin(
        self,
        admin_client: AsyncClient,
        target_user_id: object,
    ) -> None:
        """ADMN-05: Admin can promote a user to admin."""
        with patch("stockvaluefinder.api.admin_routes.UserRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_user = _make_mock_user(
                user_id=target_user_id,
                role="admin",
            )
            mock_repo.update_role = AsyncMock(return_value=mock_user)
            MockRepo.return_value = mock_repo

            response = await admin_client.patch(
                f"/api/v1/admin/users/{target_user_id}/role",
                json={"role": "admin"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["role"] == "admin"

    @pytest.mark.asyncio
    async def test_demote_admin_to_user(
        self,
        admin_client: AsyncClient,
        target_user_id: object,
    ) -> None:
        """ADMN-05: Admin can demote another admin to user."""
        with patch("stockvaluefinder.api.admin_routes.UserRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_user = _make_mock_user(
                user_id=target_user_id,
                role="user",
            )
            mock_repo.update_role = AsyncMock(return_value=mock_user)
            MockRepo.return_value = mock_repo

            response = await admin_client.patch(
                f"/api/v1/admin/users/{target_user_id}/role",
                json={"role": "user"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["role"] == "user"

    @pytest.mark.asyncio
    async def test_admin_cannot_change_own_role(
        self,
        admin_client: AsyncClient,
        admin_user_id: object,
    ) -> None:
        """RBAC-03: Admin cannot change their own role (returns 400)."""
        response = await admin_client.patch(
            f"/api/v1/admin/users/{admin_user_id}/role",
            json={"role": "user"},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_role_user_not_found(
        self,
        admin_client: AsyncClient,
    ) -> None:
        """ADMN-05: Role change for non-existent user returns 404."""
        with patch("stockvaluefinder.api.admin_routes.UserRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.update_role = AsyncMock(return_value=None)
            MockRepo.return_value = mock_repo

            response = await admin_client.patch(
                f"/api/v1/admin/users/{uuid4()}/role",
                json={"role": "admin"},
            )

            assert response.status_code == 404


# ===================================================================
# TestAdminDeleteUser  (ADMN-04)
# ===================================================================


class TestAdminDeleteUser:
    """Tests for DELETE /api/v1/admin/users/{user_id} endpoint."""

    @pytest.mark.asyncio
    async def test_soft_delete_user(
        self,
        admin_client: AsyncClient,
        target_user_id: object,
    ) -> None:
        """ADMN-04: Admin can soft-delete a user."""
        with patch("stockvaluefinder.api.admin_routes.UserRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_user = _make_mock_user(user_id=target_user_id)
            mock_repo.get_by_id = AsyncMock(return_value=mock_user)
            mock_repo.soft_delete = AsyncMock(return_value=mock_user)
            MockRepo.return_value = mock_repo

            response = await admin_client.delete(
                f"/api/v1/admin/users/{target_user_id}"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_admin_cannot_delete_self(
        self,
        admin_client: AsyncClient,
        admin_user_id: object,
    ) -> None:
        """ADMN-04: Admin cannot delete their own account (returns 400)."""
        response = await admin_client.delete(f"/api/v1/admin/users/{admin_user_id}")

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_user_not_found(
        self,
        admin_client: AsyncClient,
    ) -> None:
        """ADMN-04: Deleting non-existent user returns 404."""
        with patch("stockvaluefinder.api.admin_routes.UserRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_by_id = AsyncMock(return_value=None)
            MockRepo.return_value = mock_repo

            response = await admin_client.delete(f"/api/v1/admin/users/{uuid4()}")

            assert response.status_code == 404


# ===================================================================
# TestAdminRBACEnforcement  (RBAC-04)
# ===================================================================


class TestAdminRBACEnforcement:
    """Tests verifying that non-admin users receive 403 on all admin endpoints."""

    @pytest.mark.asyncio
    async def test_non_admin_list_users_returns_403(
        self,
        regular_client: AsyncClient,
    ) -> None:
        """RBAC-04: Non-admin receives 403 on list users."""
        response = await regular_client.get("/api/v1/admin/users")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_non_admin_get_user_returns_403(
        self,
        regular_client: AsyncClient,
    ) -> None:
        """RBAC-04: Non-admin receives 403 on get user."""
        response = await regular_client.get(f"/api/v1/admin/users/{uuid4()}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_non_admin_update_status_returns_403(
        self,
        regular_client: AsyncClient,
    ) -> None:
        """RBAC-04: Non-admin receives 403 on update status."""
        response = await regular_client.patch(
            f"/api/v1/admin/users/{uuid4()}/status",
            json={"is_active": False},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_non_admin_update_role_returns_403(
        self,
        regular_client: AsyncClient,
    ) -> None:
        """RBAC-04: Non-admin receives 403 on update role."""
        response = await regular_client.patch(
            f"/api/v1/admin/users/{uuid4()}/role",
            json={"role": "admin"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_non_admin_delete_user_returns_403(
        self,
        regular_client: AsyncClient,
    ) -> None:
        """RBAC-04: Non-admin receives 403 on delete user."""
        response = await regular_client.delete(f"/api/v1/admin/users/{uuid4()}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401_or_403(self) -> None:
        """RBAC-04: Unauthenticated requests receive 401 or 403 on admin endpoints."""
        app = FastAPI()
        app.include_router(admin_router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            follow_redirects=True,
        ) as ac:
            response = await ac.get("/api/v1/admin/users")
            assert response.status_code in (401, 403)
