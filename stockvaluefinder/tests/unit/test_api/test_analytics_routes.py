"""Tests for admin analytics and rate limit override endpoints."""

import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://dummy:dummy@localhost/dummy"

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient

from stockvaluefinder.main import app
from stockvaluefinder.db.base import get_db
from stockvaluefinder.api.dependencies import get_current_user, require_admin

# ── Fixtures ──

ADMIN_USER = {
    "user_id": "admin-001",
    "email": "admin@test.com",
    "role": "admin",
    "is_active": True,
}

NON_ADMIN_USER = {
    "user_id": "user-001",
    "email": "user@test.com",
    "role": "user",
    "is_active": True,
}

USER_UUID = "00000000-0000-0000-0000-000000000123"


def _make_admin_override():
    async def _admin():
        return ADMIN_USER

    return {require_admin: _admin, get_current_user: _admin}


def _make_non_admin_override():
    """Override only get_current_user to return non-admin; let require_admin run its real check."""
    from stockvaluefinder.api.dependencies import get_current_user

    async def _user():
        return NON_ADMIN_USER

    return {get_current_user: _user}


def _make_db_override(mock_db):
    async def _gen():
        yield mock_db

    return {get_db: _gen}


# ── Analytics Routes Tests ──


class TestGetUserUsageSummary:
    @pytest.mark.asyncio
    async def test_returns_usage_summary(self):
        mock_user = MagicMock()
        mock_user.id = USER_UUID

        mock_tracker = AsyncMock()
        mock_tracker.get_user_usage.return_value = {
            "calls:/api/v1/analyze/risk": "5",
            "total_calls": "10",
        }
        mock_tracker.get_last_active.return_value = "2026-05-11T00:00:00Z"

        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        with patch("stockvaluefinder.api.dependencies._usage_tracker", mock_tracker):
            app.dependency_overrides = {
                **_make_admin_override(),
                **_make_db_override(mock_db),
            }
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(f"/api/v1/admin/analytics/users/{USER_UUID}")
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["user_id"] == USER_UUID

    @pytest.mark.asyncio
    async def test_user_not_found_returns_404(self):
        """Returns 404 for nonexistent user."""
        mock_db = AsyncMock()

        with (
            patch("stockvaluefinder.api.dependencies._usage_tracker", None),
            patch("stockvaluefinder.api.analytics_routes.UserRepository") as MockRepo,
        ):
            mock_repo_instance = AsyncMock()
            mock_repo_instance.get_by_id.return_value = None
            MockRepo.return_value = mock_repo_instance

            app.dependency_overrides = {
                **_make_admin_override(),
                **_make_db_override(mock_db),
            }
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/analytics/users/00000000-0000-0000-0000-999999999999"
                )
            app.dependency_overrides.clear()

        assert resp.status_code == 404


class TestGetAggregateStats:
    @pytest.mark.asyncio
    async def test_returns_aggregate_stats(self):
        mock_stats = {
            "total_calls": 1000,
            "total_errors": 50,
            "top_users": [{"user_id": "u1", "total_calls": 500}],
        }
        mock_repo = AsyncMock()
        mock_repo.get_aggregate_stats.return_value = mock_stats
        mock_db = AsyncMock()

        with patch(
            "stockvaluefinder.api.analytics_routes.ApiUsageRepository",
            return_value=mock_repo,
        ):
            app.dependency_overrides = {
                **_make_admin_override(),
                **_make_db_override(mock_db),
            }
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/admin/analytics/aggregate")
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total_calls"] == 1000


# ── Rate Limit Override Tests ──


class TestGetRateLimitOverride:
    @pytest.mark.asyncio
    async def test_returns_override_when_set(self):
        from stockvaluefinder.middleware.rate_limiter import RateLimitOverride

        mock_limiter = AsyncMock()
        mock_limiter.get_user_override.return_value = RateLimitOverride(
            limit=200, window=7200
        )

        with patch(
            "stockvaluefinder.api.admin_routes.get_rate_limiter",
            return_value=mock_limiter,
        ):
            app.dependency_overrides = _make_admin_override()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(f"/api/v1/admin/users/{USER_UUID}/rate-limit")
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["data"]["limit"] == 200

    @pytest.mark.asyncio
    async def test_returns_default_when_no_override(self):
        mock_limiter = AsyncMock()
        mock_limiter.get_user_override.return_value = None

        with patch(
            "stockvaluefinder.api.admin_routes.get_rate_limiter",
            return_value=mock_limiter,
        ):
            app.dependency_overrides = _make_admin_override()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(f"/api/v1/admin/users/{USER_UUID}/rate-limit")
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["data"]["limit"] == 100
        assert resp.json()["data"]["window_seconds"] == 3600


class TestSetRateLimitOverride:
    @pytest.mark.asyncio
    async def test_creates_override(self):
        mock_user = MagicMock()
        mock_user.email = "test@test.com"

        mock_db = AsyncMock()
        # scalar_one_or_none is synchronous in SQLAlchemy, use MagicMock for result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No existing override
        mock_db.execute.return_value = mock_result

        mock_limiter = AsyncMock()

        with (
            patch(
                "stockvaluefinder.api.admin_routes.get_rate_limiter",
                return_value=mock_limiter,
            ),
            patch("stockvaluefinder.api.admin_routes.UserRepository") as MockRepo,
        ):
            mock_repo_instance = AsyncMock()
            mock_repo_instance.get_by_id.return_value = mock_user
            MockRepo.return_value = mock_repo_instance

            app.dependency_overrides = {
                **_make_admin_override(),
                **_make_db_override(mock_db),
            }
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.put(
                    f"/api/v1/admin/users/{USER_UUID}/rate-limit",
                    json={"limit": 200, "window_seconds": 7200},
                )
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["data"]["limit"] == 200
        mock_limiter.set_user_override.assert_called_once_with(USER_UUID, 200, 7200)


class TestDeleteRateLimitOverride:
    @pytest.mark.asyncio
    async def test_removes_override(self):
        mock_db = AsyncMock()
        mock_limiter = AsyncMock()

        with patch(
            "stockvaluefinder.api.admin_routes.get_rate_limiter",
            return_value=mock_limiter,
        ):
            app.dependency_overrides = {
                **_make_admin_override(),
                **_make_db_override(mock_db),
            }
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.delete(
                    f"/api/v1/admin/users/{USER_UUID}/rate-limit"
                )
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_limiter.remove_user_override.assert_called_once_with(USER_UUID)


class TestNonAdminRejected:
    @pytest.mark.asyncio
    async def test_analytics_user_summary_403(self):
        mock_db = AsyncMock()
        app.dependency_overrides = {
            **_make_non_admin_override(),
            **_make_db_override(mock_db),
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/admin/analytics/users/{USER_UUID}")
        app.dependency_overrides.clear()
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_analytics_aggregate_403(self):
        mock_db = AsyncMock()
        app.dependency_overrides = {
            **_make_non_admin_override(),
            **_make_db_override(mock_db),
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/admin/analytics/aggregate")
        app.dependency_overrides.clear()
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_rate_limit_get_403(self):
        app.dependency_overrides = _make_non_admin_override()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/admin/users/{USER_UUID}/rate-limit")
        app.dependency_overrides.clear()
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_rate_limit_put_403(self):
        mock_db = AsyncMock()
        app.dependency_overrides = {
            **_make_non_admin_override(),
            **_make_db_override(mock_db),
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"/api/v1/admin/users/{USER_UUID}/rate-limit",
                json={"limit": 200, "window_seconds": 7200},
            )
        app.dependency_overrides.clear()
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_rate_limit_delete_403(self):
        mock_db = AsyncMock()
        app.dependency_overrides = {
            **_make_non_admin_override(),
            **_make_db_override(mock_db),
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"/api/v1/admin/users/{USER_UUID}/rate-limit")
        app.dependency_overrides.clear()
        assert resp.status_code == 403
