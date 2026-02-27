"""Contract tests for DCF valuation API endpoint."""

import pytest
from httpx import AsyncClient
from pydantic import ValidationError


@pytest.mark.contract
@pytest.mark.asyncio
class TestDCFValuationAPIContract:
    """Contract tests for POST /api/v1/analyze/dcf endpoint."""

    async def test_dcf_valuation_success(self, client: AsyncClient) -> None:
        """Test successful DCF valuation request."""
        response = await client.post(
            "/api/v1/analyze/dcf",
            json={"ticker": "000002.SZ", "growth_rate_stage1": 0.05},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response envelope
        assert data["success"] is True
        assert "data" in data
        assert data["error"] is None

        # Verify DCF valuation data structure
        result = data["data"]
        assert "ticker" in result
        assert "current_price" in result
        assert "intrinsic_value" in result
        assert "wacc" in result
        assert "margin_of_safety" in result
        assert "valuation_level" in result
        assert "audit_trail" in result

        # Verify types
        assert isinstance(result["intrinsic_value"], (int, float))
        assert isinstance(result["wacc"], (int, float))
        assert isinstance(result["margin_of_safety"], (int, float))
        assert isinstance(result["valuation_level"], str)
        assert isinstance(result["audit_trail"], dict)

    async def test_dcf_valuation_with_parameters(self, client: AsyncClient) -> None:
        """Test DCF valuation with custom parameters."""
        response = await client.post(
            "/api/v1/analyze/dcf",
            json={
                "ticker": "000002.SZ",
                "growth_rate_stage1": 0.08,
                "growth_rate_stage2": 0.03,
                "years_stage1": 5,
                "years_stage2": 5,
                "terminal_growth": 0.025,
                "risk_free_rate": 0.03,
                "beta": 1.2,
                "market_risk_premium": 0.06,
            },
        )

        assert response.status_code == 200
        data = response.json()
        result = data["data"]

        # Verify custom parameters are reflected in results
        assert result["audit_trail"]["growth_rate_stage1"] == 0.08

    async def test_dcf_valuation_invalid_ticker_format(self, client: AsyncClient) -> None:
        """Test request with invalid ticker format."""
        response = await client.post(
            "/api/v1/analyze/dcf",
            json={"ticker": "INVALID", "growth_rate_stage1": 0.05},
        )

        assert response.status_code == 422  # Validation error

    async def test_dcf_valuation_missing_ticker(self, client: AsyncClient) -> None:
        """Test request with missing ticker."""
        with pytest.raises(ValidationError):
            from stockvaluefinder.models.valuation import DCFValuationRequest
            DCFValuationRequest(growth_rate_stage1=0.05)  # type: ignore

    async def test_dcf_valuation_negative_growth_rate(self, client: AsyncClient) -> None:
        """Test request with negative growth rate (should be allowed for distressed companies)."""
        response = await client.post(
            "/api/v1/analyze/dcf",
            json={"ticker": "000002.SZ", "growth_rate_stage1": -0.05},
        )

        # Should succeed (negative growth is valid)
        assert response.status_code == 200

    async def test_dcf_valuation_extreme_growth_rate(self, client: AsyncClient) -> None:
        """Test request with unrealistic growth rate."""
        response = await client.post(
            "/api/v1/analyze/dcf",
            json={"ticker": "000002.SZ", "growth_rate_stage1": 0.50},  # 50% growth
        )

        # Should succeed but may trigger warnings
        assert response.status_code == 200

    async def test_valuation_levels(self, client: AsyncClient) -> None:
        """Test different valuation levels based on margin of safety."""
        # Undervalued (MoS > 30%)
        response1 = await client.post(
            "/api/v1/analyze/dcf",
            json={"ticker": "000002.SZ", "growth_rate_stage1": 0.10},
        )
        assert response1.status_code == 200
        result1 = response1.json()["data"]
        assert result1["valuation_level"] in ["UNDERVERLUED", "FAIR_VALUE", "OVERVALUED"]

    async def test_dcf_audit_trail_completeness(self, client: AsyncClient) -> None:
        """Test that audit trail contains all calculation steps."""
        response = await client.post(
            "/api/v1/analyze/dcf",
            json={"ticker": "000002.SZ", "growth_rate_stage1": 0.05},
        )

        assert response.status_code == 200
        data = response.json()
        audit_trail = data["data"]["audit_trail"]

        # Verify audit trail contains all steps
        assert "wacc" in audit_trail
        assert "fcf_projections" in audit_trail
        assert "present_values" in audit_trail
        assert "terminal_value" in audit_trail
        assert "intrinsic_value" in audit_trail
        assert "margin_of_safety" in audit_trail
