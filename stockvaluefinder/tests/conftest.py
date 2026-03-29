"""Shared pytest fixtures."""

import pytest
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

# Import routers
from stockvaluefinder.api.risk_routes import router as risk_router
from stockvaluefinder.api.yield_routes import router as yield_router
from stockvaluefinder.api.valuation_routes import router as valuation_router

# TODO: Create test database fixtures
# - async database session
# - mock external API clients
# - test data factories
# - cache client mock


@pytest.fixture
async def db_session() -> AsyncSession:
    """Fixture for test database session."""
    # TODO: Implement test session
    raise NotImplementedError("Test fixture not yet implemented")


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Fixture for HTTP client with FastAPI app."""
    # Create FastAPI app and include all routers
    app = FastAPI()
    app.include_router(risk_router)
    app.include_router(yield_router)
    app.include_router(valuation_router)

    # Create AsyncClient with ASGI transport
    # Note: follow_redirects=False to avoid 307 redirects when trailing slash is missing
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=True,
    ) as ac:
        yield ac
