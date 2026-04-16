"""Integration tests for POST /api/v1/analyze/risk.

Per D-04: Full E2E test exercising route -> service -> repo -> DB -> response.
External data sources are mocked (DEVELOPMENT_MODE=true); database is real.
"""

import pytest


@pytest.mark.skip_if_no_db
class TestRiskAPI:
    """E2E tests for risk analysis endpoint."""

    async def test_risk_analysis_returns_success_envelope(self, client) -> None:
        """POST /api/v1/analyze/risk returns ApiResponse with success=True."""
        response = await client.post(
            "/api/v1/analyze/risk",
            json={"ticker": "600519.SH"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"] is not None
        assert body["error"] is None

    async def test_risk_analysis_data_has_required_fields(self, client) -> None:
        """Risk analysis result contains m_score, f_score, risk_level, red_flags."""
        response = await client.post(
            "/api/v1/analyze/risk",
            json={"ticker": "600519.SH"},
        )
        body = response.json()
        data = body["data"]
        assert "m_score" in data
        assert "f_score" in data
        assert "risk_level" in data
        assert "red_flags" in data
        assert data["risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    async def test_risk_analysis_with_invalid_ticker(self, client) -> None:
        """Invalid ticker returns validation error (422)."""
        response = await client.post(
            "/api/v1/analyze/risk",
            json={"ticker": "INVALID"},
        )
        assert response.status_code == 422
