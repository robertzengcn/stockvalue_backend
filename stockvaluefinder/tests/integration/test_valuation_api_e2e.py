"""Integration tests for POST /api/v1/analyze/dcf.

Per D-04: Full E2E test exercising route -> service -> repo -> DB -> response.
External data sources are mocked (DEVELOPMENT_MODE=true); database is real.
"""

import pytest


@pytest.mark.skip_if_no_db
class TestValuationAPI:
    """E2E tests for DCF valuation endpoint."""

    async def test_dcf_valuation_returns_success_envelope(self, client) -> None:
        """POST /api/v1/analyze/dcf returns ApiResponse with success=True."""
        response = await client.post(
            "/api/v1/analyze/dcf",
            json={"ticker": "600519.SH"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"] is not None

    async def test_dcf_valuation_data_has_required_fields(self, client) -> None:
        """DCF result contains intrinsic_value, wacc, margin_of_safety, valuation_level."""
        response = await client.post(
            "/api/v1/analyze/dcf",
            json={"ticker": "600519.SH"},
        )
        body = response.json()
        data = body["data"]
        assert "intrinsic_value" in data
        assert "wacc" in data
        assert "margin_of_safety" in data
        assert "valuation_level" in data
        assert data["valuation_level"] in ["UNDERVALUED", "FAIR_VALUE", "OVERVALUED"]

    async def test_dcf_valuation_with_invalid_ticker(self, client) -> None:
        """Invalid ticker returns validation error (422)."""
        response = await client.post(
            "/api/v1/analyze/dcf",
            json={"ticker": "INVALID"},
        )
        assert response.status_code == 422
