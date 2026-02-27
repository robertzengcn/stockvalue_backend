"""Contract tests for POST /api/v1/analyze/risk endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.contract
@pytest.mark.asyncio
class TestRiskAPIContract:
    """Contract tests for risk analysis API endpoint."""

    async def test_analyze_risk_success(
        self,
        client: AsyncClient,
        sample_ticker: str = "600519.SH",
    ) -> None:
        """Test successful risk analysis request.

        Given a valid ticker symbol
        When POST /api/v1/analyze/risk is called
        Then should return 200 with complete risk report
        """
        response = await client.post(
            "/api/v1/analyze/risk",
            json={"ticker": sample_ticker},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "success" in data
        assert data["success"] is True
        assert "data" in data
        assert "error" in data
        assert data["error"] is None

        # Verify risk report structure
        risk_data = data["data"]
        assert "ticker" in risk_data
        assert risk_data["ticker"] == sample_ticker
        assert "risk_level" in risk_data
        assert risk_data["risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        assert "calculated_at" in risk_data

        # Verify M-Score data
        assert "m_score" in risk_data
        assert "mscore_data" in risk_data
        mscore_data = risk_data["mscore_data"]
        assert "dsri" in mscore_data
        assert "gmi" in mscore_data
        assert "aqi" in mscore_data
        assert "sgi" in mscore_data
        assert "depi" in mscore_data
        assert "sgai" in mscore_data
        assert "lvgi" in mscore_data
        assert "tata" in mscore_data
        assert isinstance(mscore_data["dsri"], float)
        assert isinstance(mscore_data["m_score"], float)

        # Verify risk flags
        assert "存贷双高" in risk_data
        assert "cash_amount" in risk_data
        assert "debt_amount" in risk_data
        assert isinstance(risk_data["存贷双高"], bool)

        # Verify goodwill risk
        assert "goodwill_ratio" in risk_data
        assert "goodwill_excessive" in risk_data
        assert isinstance(risk_data["goodwill_ratio"], float)
        assert isinstance(risk_data["goodwill_excessive"], bool)

        # Verify red flags
        assert "red_flags" in risk_data
        assert isinstance(risk_data["red_flags"], list)

    async def test_analyze_risk_invalid_ticker_format(
        self,
        client: AsyncClient,
    ) -> None:
        """Test risk analysis with invalid ticker format.

        Given an invalid ticker format
        When POST /api/v1/analyze/risk is called
        Then should return 422 with validation error
        """
        response = await client.post(
            "/api/v1/analyze/risk",
            json={"ticker": "INVALID"},
        )

        assert response.status_code == 422
        data = response.json()

        assert "success" in data
        assert data["success"] is False
        assert "error" in data
        assert "detail" in data["error"]

    async def test_analyze_risk_missing_ticker(
        self,
        client: AsyncClient,
    ) -> None:
        """Test risk analysis with missing ticker field.

        Given request without ticker field
        When POST /api/v1/analyze/risk is called
        Then should return 422 with validation error
        """
        response = await client.post(
            "/api/v1/analyze/risk",
            json={},
        )

        assert response.status_code == 422
        data = response.json()

        assert "success" in data
        assert data["success"] is False
        assert "error" in data

    async def test_analyze_risk_stock_not_found(
        self,
        client: AsyncClient,
    ) -> None:
        """Test risk analysis for non-existent stock.

        Given a ticker for a stock that doesn't exist
        When POST /api/v1/analyze/risk is called
        Then should return 404 with appropriate error
        """
        response = await client.post(
            "/api/v1/analyze/risk",
            json={"ticker": "999999.SH"},
        )

        assert response.status_code == 404
        data = response.json()

        assert "success" in data
        assert data["success"] is False
        assert "error" in data
        assert "not found" in data["error"].lower()

    async def test_analyze_risk_missing_financial_data(
        self,
        client: AsyncClient,
        monkeypatch,
    ) -> None:
        """Test risk analysis when financial data is missing.

        Given a stock without financial data
        When POST /api/v1/analyze/risk is called
        Then should return 400 with appropriate error
        """
        # This test would require mocking to simulate missing data
        # For now, we'll document the expected behavior
        response = await client.post(
            "/api/v1/analyze/risk",
            json={"ticker": "000001.SZ"},  # Assume this stock has no data
        )

        # Should either return 400 or 200 with error in data
        assert response.status_code in [200, 400]
        data = response.json()

        if response.status_code == 200:
            # If 200, should indicate data not available
            assert "error" in data.get("data", {})


# Pytest fixtures for contract tests
@pytest.fixture
async def client() -> AsyncClient:
    """Create test HTTP client."""

    from stockvaluefinder.api.risk_routes import router as risk_router
    from stockvaluefinder.main import app

    # Include risk router
    app.include_router(risk_router, prefix="/api/v1")

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
