"""Integration test fixtures with real PostgreSQL test database.

Per D-04: Full E2E tests with database (route->service->repo->DB->response).
Per D-05: Separate test database (stockvaluefinder_test) on the same PostgreSQL instance.
External data sources (AKShare/efinance) are mocked; database is real.
"""

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Test database URL (per D-05: separate stockvaluefinder_test database)
TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://svf_admin:Fo41_2vhaOHKnBAyMUToMA@localhost:5433/stockvaluefinder_test",
)


def _db_available() -> bool:
    """Check if PostgreSQL test database is accessible."""
    import asyncio

    try:
        engine = create_async_engine(TEST_DB_URL, pool_size=1)

        async def _check() -> None:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()

        asyncio.get_event_loop().run_until_complete(_check())
        return True
    except Exception:
        return False


# Skip marker for integration tests when DB unavailable
skip_if_no_db = pytest.mark.skipif(
    not _db_available(),
    reason="PostgreSQL test database not available on localhost:5433",
)


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine and tables (session-scoped).

    Creates all tables on first use and drops them after the session ends.
    Uses the same async engine pattern as the production codebase.
    """
    # Import all models so Base.metadata knows about them
    from stockvaluefinder.db.models import (  # noqa: F401
        DividendDataDB,
        FinancialReportDB,
        RateDataDB,
        RiskScoreDB,
        StockDB,
        ValuationResultDB,
        YieldGapDB,
    )
    from stockvaluefinder.db.base import Base

    engine = create_async_engine(TEST_DB_URL, echo=False, pool_size=5)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables after session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session that rolls back after each test.

    Each test gets a fresh session. After the test, the session is rolled
    back to isolate test data (per T-03-06: prevent test DB data leakage).
    """
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_engine: AsyncEngine) -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient with DB and data service dependencies overridden.

    Overrides:
    - get_db: routes to test database with per-test rollback
    - get_initialized_data_service: mock data service (no external API calls)

    This allows testing the full route->service->repo->DB->response cycle
    without touching external data sources.
    """
    from stockvaluefinder.db.base import get_db
    from stockvaluefinder.api.dependencies import get_initialized_data_service
    from stockvaluefinder.external.data_service import ExternalDataService
    from stockvaluefinder.main import app

    # Build session factory for test database
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        """Yield test DB session with auto-rollback."""
        async with session_factory() as session:
            yield session

    # Override data service with mocked external sources (no real API calls)
    mock_data_service = ExternalDataService(
        tushare_token="",
        enable_akshare=False,
        enable_efinance=False,
    )

    async def override_get_data_service() -> AsyncGenerator[ExternalDataService, None]:
        """Yield mock data service instead of real external sources."""
        yield mock_data_service

    # Override FastAPI dependencies
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_initialized_data_service] = override_get_data_service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=True,
    ) as ac:
        yield ac

    # Clean up overrides after test
    app.dependency_overrides.clear()
