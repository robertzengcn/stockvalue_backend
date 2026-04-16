"""Integration tests for POST /api/v1/analyze/yield.

Per D-04: Full E2E test exercising route -> service -> repo -> DB -> response.
External data sources are mocked (DEVELOPMENT_MODE=true); database is real.
"""

import pytest


@pytest.mark.skip_if_no_db
class TestYieldAPI:
    """E2E tests for yield gap analysis endpoint."""

    async def test_yield_analysis_returns_success_envelope(self, client) -> None:
        """POST /api/v1/analyze/yield returns ApiResponse with success=True."""
        response = await client.post(
            "/api/v1/analyze/yield",
            json={"ticker": "600519.SH", "cost_basis": 1800.0},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"] is not None

    async def test_yield_analysis_data_has_required_fields(self, client) -> None:
        """Yield result contains net_dividend_yield, yield_gap, recommendation."""
        response = await client.post(
            "/api/v1/analyze/yield",
            json={"ticker": "600519.SH", "cost_basis": 1800.0},
        )
        body = response.json()
        data = body["data"]
        assert "net_dividend_yield" in data
        assert "yield_gap" in data
        assert "recommendation" in data
        assert data["recommendation"] in ["ATTRACTIVE", "NEUTRAL", "UNATTRACTIVE"]

    async def test_yield_analysis_with_invalid_ticker(self, client) -> None:
        """Invalid ticker returns validation error (422)."""
        response = await client.post(
            "/api/v1/analyze/yield",
            json={"ticker": "INVALID", "cost_basis": 1800.0},
        )
        assert response.status_code == 422

    async def test_yield_analysis_with_negative_cost_basis(self, client) -> None:
        """Negative cost_basis returns validation error (422)."""
        response = await client.post(
            "/api/v1/analyze/yield",
            json={"ticker": "600519.SH", "cost_basis": -100.0},
        )
        assert response.status_code == 422
