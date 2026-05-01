"""Unit tests for the pipeline health-check endpoint.

Tests the GET /api/v1/pipeline/health endpoint which checks
Redis, PostgreSQL, worker queue, and watcher component health.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from stockvaluefinder.api.pipeline_routes import router as pipeline_router


def _create_app_with_pool(pool: AsyncMock | None) -> FastAPI:
    """Create a FastAPI app with the pipeline router and a mock arq pool.

    Args:
        pool: Mock arq pool to set on app.state, or None.

    Returns:
        FastAPI app with pipeline router registered.
    """
    app = FastAPI()
    app.include_router(pipeline_router)
    app.state.arq_pool = pool
    return app


def _mock_healthy_session_maker() -> MagicMock:
    """Create a mock async_session_maker with a successful execute."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=None)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=mock_session)


def _mock_failing_session_maker() -> MagicMock:
    """Create a mock async_session_maker with a failing execute."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=Exception("DB connection lost"))
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=mock_session)


SESSION_MAKER_PATH = "stockvaluefinder.api.pipeline_routes.async_session_maker"


class TestHealthEndpointHealthy:
    """Tests for healthy pipeline state."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self):
        """Health endpoint returns 200 status code."""
        mock_pool = AsyncMock()
        mock_pool.ping = AsyncMock(return_value=True)
        app = _create_app_with_pool(mock_pool)

        with patch(SESSION_MAKER_PATH, _mock_healthy_session_maker()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_returns_success_true(self):
        """Health endpoint returns success=True in response."""
        mock_pool = AsyncMock()
        mock_pool.ping = AsyncMock(return_value=True)
        app = _create_app_with_pool(mock_pool)

        with patch(SESSION_MAKER_PATH, _mock_healthy_session_maker()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")
                data = response.json()
                assert data["success"] is True

    @pytest.mark.asyncio
    async def test_health_contains_status_field(self):
        """Response data contains status field."""
        mock_pool = AsyncMock()
        mock_pool.ping = AsyncMock(return_value=True)
        app = _create_app_with_pool(mock_pool)

        with patch(SESSION_MAKER_PATH, _mock_healthy_session_maker()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")
                data = response.json()
                assert "status" in data["data"]

    @pytest.mark.asyncio
    async def test_health_healthy_when_all_up(self):
        """Status is healthy when all components are up."""
        mock_pool = AsyncMock()
        mock_pool.ping = AsyncMock(return_value=True)
        app = _create_app_with_pool(mock_pool)

        with patch(SESSION_MAKER_PATH, _mock_healthy_session_maker()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")
                data = response.json()
                assert data["data"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_contains_components(self):
        """Response data contains components dict with all expected keys."""
        mock_pool = AsyncMock()
        mock_pool.ping = AsyncMock(return_value=True)
        app = _create_app_with_pool(mock_pool)

        with patch(SESSION_MAKER_PATH, _mock_healthy_session_maker()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")
                data = response.json()
                components = data["data"]["components"]
                assert "redis" in components
                assert "postgresql" in components
                assert "worker" in components
                assert "watcher" in components

    @pytest.mark.asyncio
    async def test_redis_healthy_when_ping_succeeds(self):
        """Redis component reports healthy when PING succeeds."""
        mock_pool = AsyncMock()
        mock_pool.ping = AsyncMock(return_value=True)
        app = _create_app_with_pool(mock_pool)

        with patch(SESSION_MAKER_PATH, _mock_healthy_session_maker()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")
                data = response.json()
                assert data["data"]["components"]["redis"] == "healthy"

    @pytest.mark.asyncio
    async def test_postgresql_healthy_when_select_succeeds(self):
        """PostgreSQL component reports healthy when SELECT 1 succeeds."""
        mock_pool = AsyncMock()
        mock_pool.ping = AsyncMock(return_value=True)
        app = _create_app_with_pool(mock_pool)

        with patch(SESSION_MAKER_PATH, _mock_healthy_session_maker()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")
                data = response.json()
                assert data["data"]["components"]["postgresql"] == "healthy"

    @pytest.mark.asyncio
    async def test_worker_healthy_when_redis_healthy(self):
        """Worker reports healthy when Redis is healthy."""
        mock_pool = AsyncMock()
        mock_pool.ping = AsyncMock(return_value=True)
        app = _create_app_with_pool(mock_pool)

        with patch(SESSION_MAKER_PATH, _mock_healthy_session_maker()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")
                data = response.json()
                assert data["data"]["components"]["worker"] == "healthy"

    @pytest.mark.asyncio
    async def test_watcher_not_configured(self):
        """Watcher component always reports not_configured in Phase 5."""
        mock_pool = AsyncMock()
        mock_pool.ping = AsyncMock(return_value=True)
        app = _create_app_with_pool(mock_pool)

        with patch(SESSION_MAKER_PATH, _mock_healthy_session_maker()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")
                data = response.json()
                assert data["data"]["components"]["watcher"] == "not_configured"

    @pytest.mark.asyncio
    async def test_checked_at_is_iso_format(self):
        """checked_at contains a valid ISO format datetime string."""
        mock_pool = AsyncMock()
        mock_pool.ping = AsyncMock(return_value=True)
        app = _create_app_with_pool(mock_pool)

        with patch(SESSION_MAKER_PATH, _mock_healthy_session_maker()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")
                data = response.json()
                checked_at = data["data"]["checked_at"]
                # Should parse without error
                parsed = datetime.fromisoformat(checked_at)
                assert parsed is not None


class TestHealthEndpointRedisDown:
    """Tests for when Redis is unhealthy."""

    @pytest.mark.asyncio
    async def test_redis_unhealthy_when_ping_fails(self):
        """Redis component reports unhealthy when PING raises exception."""
        mock_pool = AsyncMock()
        mock_pool.ping = AsyncMock(side_effect=Exception("Connection refused"))
        app = _create_app_with_pool(mock_pool)

        with patch(SESSION_MAKER_PATH, _mock_healthy_session_maker()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")
                data = response.json()
                assert data["data"]["components"]["redis"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_overall_degraded_when_redis_down(self):
        """Overall status is degraded when Redis is down."""
        mock_pool = AsyncMock()
        mock_pool.ping = AsyncMock(side_effect=Exception("Connection refused"))
        app = _create_app_with_pool(mock_pool)

        with patch(SESSION_MAKER_PATH, _mock_healthy_session_maker()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")
                data = response.json()
                assert data["data"]["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_worker_unreachable_when_redis_down(self):
        """Worker reports unreachable when Redis is down."""
        mock_pool = AsyncMock()
        mock_pool.ping = AsyncMock(side_effect=Exception("Connection refused"))
        app = _create_app_with_pool(mock_pool)

        with patch(SESSION_MAKER_PATH, _mock_healthy_session_maker()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")
                data = response.json()
                assert data["data"]["components"]["worker"] == "unreachable"


class TestHealthEndpointRedisNotConfigured:
    """Tests for when Redis pool is not configured."""

    @pytest.mark.asyncio
    async def test_redis_not_configured(self):
        """Redis component reports not_configured when no pool exists."""
        app = _create_app_with_pool(None)

        with patch(SESSION_MAKER_PATH, _mock_healthy_session_maker()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")
                data = response.json()
                assert data["data"]["components"]["redis"] == "not_configured"

    @pytest.mark.asyncio
    async def test_overall_degraded_when_no_pool(self):
        """Overall status is degraded when worker is unreachable (no Redis pool)."""
        app = _create_app_with_pool(None)

        with patch(SESSION_MAKER_PATH, _mock_healthy_session_maker()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")
                data = response.json()
                # Worker is unreachable when no pool, so overall is degraded
                assert data["data"]["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_worker_unreachable_when_no_pool(self):
        """Worker reports unreachable when there is no Redis pool."""
        app = _create_app_with_pool(None)

        with patch(SESSION_MAKER_PATH, _mock_healthy_session_maker()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")
                data = response.json()
                assert data["data"]["components"]["worker"] == "unreachable"


class TestHealthEndpointPostgreSQLDown:
    """Tests for when PostgreSQL is unhealthy."""

    @pytest.mark.asyncio
    async def test_postgresql_unhealthy_when_select_fails(self):
        """PostgreSQL component reports unhealthy when SELECT 1 fails."""
        mock_pool = AsyncMock()
        mock_pool.ping = AsyncMock(return_value=True)
        app = _create_app_with_pool(mock_pool)

        with patch(SESSION_MAKER_PATH, _mock_failing_session_maker()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")
                data = response.json()
                assert data["data"]["components"]["postgresql"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_overall_degraded_when_postgresql_down(self):
        """Overall status is degraded when PostgreSQL is down."""
        mock_pool = AsyncMock()
        mock_pool.ping = AsyncMock(return_value=True)
        app = _create_app_with_pool(mock_pool)

        with patch(SESSION_MAKER_PATH, _mock_failing_session_maker()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")
                data = response.json()
                assert data["data"]["status"] == "degraded"


class TestHealthEndpointAllDown:
    """Tests for when both Redis and PostgreSQL are down."""

    @pytest.mark.asyncio
    async def test_all_components_report_correctly(self):
        """When Redis and PostgreSQL are both down, all report correctly."""
        mock_pool = AsyncMock()
        mock_pool.ping = AsyncMock(side_effect=Exception("Redis down"))
        app = _create_app_with_pool(mock_pool)

        with patch(SESSION_MAKER_PATH, _mock_failing_session_maker()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/health")
                data = response.json()
                assert data["data"]["status"] == "degraded"
                assert data["data"]["components"]["redis"] == "unhealthy"
                assert data["data"]["components"]["postgresql"] == "unhealthy"
                assert data["data"]["components"]["worker"] == "unreachable"
                assert data["data"]["components"]["watcher"] == "not_configured"
