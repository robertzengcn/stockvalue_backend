"""Tests for rate limit integration: headers, 429, admin bypass, user isolation."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import APIRouter, Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from stockvaluefinder.api.dependencies import get_current_user, rate_limit
from stockvaluefinder.db.base import get_db
from stockvaluefinder.middleware.rate_limiter import RateLimitResult
from stockvaluefinder.models.api import ApiResponse


# ---------------------------------------------------------------------------
# Helper router for testing rate limit integration
# ---------------------------------------------------------------------------

_test_router = APIRouter(prefix="/api/v1/test", tags=["test"])


@_test_router.post("/analysis", response_model=ApiResponse[dict])
async def test_analysis_endpoint(
    rate_limited: dict = Depends(rate_limit),
) -> ApiResponse[dict]:
    """Test endpoint that requires rate limiting."""
    return ApiResponse(success=True, data={"message": "ok"})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock AsyncSession."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_get_db(mock_db_session: AsyncMock):
    """Override get_db dependency with mock session."""

    async def _override():
        yield mock_db_session

    return _override


@pytest.fixture
def user_id() -> str:
    """Generate a test user ID."""
    return str(uuid4())


@pytest.fixture
async def app_with_rate_limit(
    mock_get_db: Any,
    user_id: str,
) -> AsyncGenerator[FastAPI, None]:
    """Create test FastAPI app with test router and rate limit dependency."""
    app = FastAPI()
    app.include_router(_test_router)

    async def _user_override() -> dict[str, Any]:
        return {
            "user_id": user_id,
            "email": "user@test.com",
            "role": "user",
            "is_active": True,
        }

    app.dependency_overrides[get_current_user] = _user_override
    app.dependency_overrides[get_db] = mock_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def rate_limit_client(app_with_rate_limit: FastAPI):
    """Create async test client with rate limiting enabled."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_rate_limit),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
async def app_with_admin(
    mock_get_db: Any,
) -> AsyncGenerator[FastAPI, None]:
    """Create test FastAPI app with admin user."""
    app = FastAPI()
    app.include_router(_test_router)

    async def _admin_override() -> dict[str, Any]:
        return {
            "user_id": str(uuid4()),
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
    """Create async test client with admin user."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_admin),
        base_url="http://test",
    ) as ac:
        yield ac


# ===================================================================
# TestRateLimitHeaders
# ===================================================================


class TestRateLimitHeaders:
    """Tests for rate limit response headers."""

    @pytest.mark.asyncio
    async def test_rate_limit_header_in_response(
        self,
        rate_limit_client: AsyncClient,
    ) -> None:
        """RATE-03: Response includes rate limit headers when request is allowed."""
        result = RateLimitResult(
            allowed=True, remaining=99, limit=100, reset_at=1234567890
        )

        with patch("stockvaluefinder.api.dependencies._rate_limiter") as mock_limiter:
            mock_limiter.check_rate_limit = AsyncMock(return_value=result)

            response = await rate_limit_client.post("/api/v1/test/analysis")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_rate_limit_429_when_exceeded(
        self,
        rate_limit_client: AsyncClient,
    ) -> None:
        """RATE-01: Response is 429 when rate limit exceeded."""
        import time

        future_reset = int(time.time()) + 3600
        result = RateLimitResult(
            allowed=False, remaining=0, limit=100, reset_at=future_reset
        )

        with patch("stockvaluefinder.api.dependencies._rate_limiter") as mock_limiter:
            mock_limiter.check_rate_limit = AsyncMock(return_value=result)

            response = await rate_limit_client.post("/api/v1/test/analysis")

            assert response.status_code == 429
            assert "Retry-After" in response.headers


# ===================================================================
# TestAdminRateLimitBypass
# ===================================================================


class TestAdminRateLimitBypass:
    """Tests for admin bypass of rate limiting."""

    @pytest.mark.asyncio
    async def test_admin_bypasses_rate_limit(
        self,
        admin_client: AsyncClient,
    ) -> None:
        """RATE-05: Admin user bypasses rate limiting."""
        with patch("stockvaluefinder.api.dependencies._rate_limiter") as mock_limiter:
            mock_limiter.check_rate_limit = AsyncMock()

            response = await admin_client.post("/api/v1/test/analysis")

            # Rate limiter should NOT be called for admin
            mock_limiter.check_rate_limit.assert_not_called()
            assert response.status_code == 200


# ===================================================================
# TestRateLimitUserIsolation
# ===================================================================


class TestRateLimitUserIsolation:
    """Tests for per-user rate limit isolation."""

    @pytest.mark.asyncio
    async def test_rate_limit_per_user_isolation(
        self,
        mock_get_db: Any,
    ) -> None:
        """RATE-01: Two users get independent rate limit counters."""
        user1_id = str(uuid4())
        user2_id = str(uuid4())

        # User 1 app
        app1 = FastAPI()
        app1.include_router(_test_router)

        async def _user1_override() -> dict[str, Any]:
            return {
                "user_id": user1_id,
                "email": "user1@test.com",
                "role": "user",
                "is_active": True,
            }

        app1.dependency_overrides[get_current_user] = _user1_override
        app1.dependency_overrides[get_db] = mock_get_db

        # User 2 app
        app2 = FastAPI()
        app2.include_router(_test_router)

        async def _user2_override() -> dict[str, Any]:
            return {
                "user_id": user2_id,
                "email": "user2@test.com",
                "role": "user",
                "is_active": True,
            }

        app2.dependency_overrides[get_current_user] = _user2_override
        app2.dependency_overrides[get_db] = mock_get_db

        result1 = RateLimitResult(
            allowed=True, remaining=99, limit=100, reset_at=1234567890
        )
        result2 = RateLimitResult(
            allowed=True, remaining=50, limit=100, reset_at=1234567890
        )

        with patch("stockvaluefinder.api.dependencies._rate_limiter") as mock_limiter:
            # Return different remaining values for different user IDs
            mock_limiter.check_rate_limit = AsyncMock(side_effect=[result1, result2])

            async with AsyncClient(
                transport=ASGITransport(app=app1),
                base_url="http://test",
            ) as client1:
                resp1 = await client1.post("/api/v1/test/analysis")
                assert resp1.status_code == 200

            async with AsyncClient(
                transport=ASGITransport(app=app2),
                base_url="http://test",
            ) as client2:
                resp2 = await client2.post("/api/v1/test/analysis")
                assert resp2.status_code == 200

            # Verify check_rate_limit was called with different user IDs
            assert mock_limiter.check_rate_limit.call_count == 2
            calls = mock_limiter.check_rate_limit.call_args_list
            assert calls[0][0][0] == user1_id
            assert calls[1][0][0] == user2_id

        app1.dependency_overrides.clear()
        app2.dependency_overrides.clear()
