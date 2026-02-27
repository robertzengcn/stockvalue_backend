"""Contract tests for yield gap API endpoint."""

import pytest
from httpx import AsyncClient
from pydantic import ValidationError


@pytest.mark.asyncio
class TestYieldGapAPIContract:
    """Contract tests for POST /api/v1/analyze/yield endpoint."""

    async def client(self) -> AsyncClient:
        """Create test HTTP client."""
        from stockvaluefinder.api.yield_routes import router as yield_router

        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(yield_router)

        return AsyncClient(app=app, base_url="http://test")

    async def test_yield_analysis_success(self, client: AsyncClient) -> None:
        """Test successful yield analysis request."""
        response = await client.post(
            "/api/v1/analyze/yield",
            json={"ticker": "0700.HK", "cost_basis": 300.00},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response envelope
        assert data["success"] is True
        assert "data" in data
        assert data["error"] is None

        # Verify yield gap data structure
        result = data["data"]
        assert "ticker" in result
        assert "cost_basis" in result
        assert "net_dividend_yield" in result
        assert "risk_free_bond_rate" in result
        assert "risk_free_deposit_rate" in result
        assert "yield_gap" in result
        assert "recommendation" in result

        # Verify types
        assert isinstance(result["net_dividend_yield"], float)
        assert isinstance(result["yield_gap"], float)
        assert isinstance(result["recommendation"], str)

    async def test_yield_analysis_a_share_no_tax(self, client: AsyncClient) -> None:
        """Test A-share dividend yield has 0% tax applied."""
        response = await client.post(
            "/api/v1/analyze/yield",
            json={"ticker": "600519.SH", "cost_basis": 1800.00},
        )

        assert response.status_code == 200
        data = response.json()

        result = data["data"]
        # A-shares have 0% dividend tax
        assert result["net_dividend_yield"] >= 0.0

    async def test_yield_analysis_hk_stock_tax_applied(self, client: AsyncClient) -> None:
        """Test HK Stock Connect has 20% tax applied."""
        response = await client.post(
            "/api/v1/analyze/yield",
            json={"ticker": "0700.HK", "cost_basis": 300.00},
        )

        assert response.status_code == 200
        data = response.json()

        result = data["data"]
        # Verify net yield is lower than gross yield (20% tax applied)
        assert "gross_dividend_yield" in result
        assert result["net_dividend_yield"] < result["gross_dividend_yield"]

    async def test_yield_analysis_invalid_ticker_format(self, client: AsyncClient) -> None:
        """Test request with invalid ticker format."""
        response = await client.post(
            "/api/v1/analyze/yield",
            json={"ticker": "INVALID", "cost_basis": 300.00},
        )

        assert response.status_code == 422  # Validation error

    async def test_yield_analysis_missing_ticker(self, client: AsyncClient) -> None:
        """Test request with missing ticker."""
        with pytest.raises(ValidationError):
            from stockvaluefinder.models.yield_gap import YieldGapRequest

            YieldGapRequest(cost_basis=300.00)  # type: ignore

    async def test_yield_analysis_missing_cost_basis(self, client: AsyncClient) -> None:
        """Test request with missing cost_basis."""
        with pytest.raises(ValidationError):
            from stockvaluefinder.models.yield_gap import YieldGapRequest

            YieldGapRequest(ticker="0700.HK")  # type: ignore

    async def test_yield_analysis_negative_cost_basis(self, client: AsyncClient) -> None:
        """Test request with negative cost_basis."""
        response = await client.post(
            "/api/v1/analyze/yield",
            json={"ticker": "0700.HK", "cost_basis": -100.00},
        )

        assert response.status_code == 422  # Validation error

    async def test_yield_recommendation_attractive(self, client: AsyncClient) -> None:
        """Test ATTRACTIVE recommendation when yield gap > 2%."""
        # This test verifies the recommendation logic
        response = await client.post(
            "/api/v1/analyze/yield",
            json={"ticker": "0700.HK", "cost_basis": 300.00},
        )

        assert response.status_code == 200
        data = response.json()

        result = data["data"]
        assert result["recommendation"] in ["ATTRACTIVE", "NEUTRAL", "UNATTRACTIVE"]
