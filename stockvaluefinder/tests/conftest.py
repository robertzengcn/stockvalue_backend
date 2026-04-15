"""Shared pytest fixtures."""

import pytest
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4
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


@pytest.fixture
def make_financial_report():
    """Factory for financial report dicts with Moutai-like defaults (per D-08).

    Returns realistic financial data for 600519.SH (Kweichow Moutai).
    Override specific fields via kwargs: make_financial_report(revenue=0)
    """

    def _factory(
        ticker: str = "600519.SH",
        year: int = 2023,
        **overrides: Any,
    ) -> dict[str, Any]:
        defaults: dict[str, Any] = {
            "ticker": ticker,
            "fiscal_year": year,
            "report_id": str(uuid4()),
            "report_source": "test",
            "revenue": 127554000000,
            "net_income": 74734000000,
            "operating_cash_flow": 58150000000,
            "accounts_receivable": 3500000000,
            "cost_of_goods": 15840000000,
            "total_current_assets": 180000000000,
            "total_assets": 255000000000,
            "assets_total": 255000000000,
            "ppe": 25000000000,
            "sga_expense": 4500000000,
            "total_liabilities": 75000000000,
            "liabilities_total": 75000000000,
            "cash_and_equivalents": 150000000000,
            "interest_bearing_debt": 2000000000,
            "goodwill": 500000000,
            "equity_total": 180000000000,
            "gross_margin": 0.876,
            "shares_outstanding": 1256197900,
        }
        return {**defaults, **overrides}

    return _factory


@pytest.fixture
def make_risk_report_pair(make_financial_report):
    """Factory for two-year financial report pairs (current + previous).

    Used for M-Score, F-Score, and YoY calculations.
    Returns (current_report, previous_report) tuple.
    """

    def _factory(
        ticker: str = "600519.SH",
        current_year: int = 2023,
        previous_year: int = 2022,
        **current_overrides: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        previous_overrides = current_overrides.pop("previous_overrides", {})
        current = make_financial_report(
            ticker=ticker, year=current_year, **current_overrides
        )
        # Previous year has slightly different values for realistic YoY changes
        previous_defaults: dict[str, Any] = {
            "revenue": 124100000000,
            "net_income": 62716000000,
            "operating_cash_flow": 51530000000,
            "accounts_receivable": 3200000000,
            "cost_of_goods": 15340000000,
            "total_current_assets": 170000000000,
            "total_assets": 245000000000,
            "assets_total": 245000000000,
            "ppe": 23000000000,
            "sga_expense": 4200000000,
            "total_liabilities": 70000000000,
            "liabilities_total": 70000000000,
            "cash_and_equivalents": 140000000000,
            "interest_bearing_debt": 1800000000,
            "goodwill": 480000000,
            "equity_total": 175000000000,
            "gross_margin": 0.876,
            "shares_outstanding": 1256197900,
        }
        previous_overrides_merged = {**previous_defaults, **previous_overrides}
        previous = make_financial_report(
            ticker=ticker, year=previous_year, **previous_overrides_merged
        )
        return current, previous

    return _factory
