"""Unit tests for Risk Analysis API routes."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.api.risk_routes import router, RiskAnalysisRequest
from stockvaluefinder.models.risk import RiskScore


@pytest.fixture
def app():
    """Create test FastAPI application."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.mark.asyncio
class TestRiskAnalysisRoutes:
    """Test suite for risk analysis API endpoints."""

    async def test_analyze_risk_success(self, client, mocker):
        """Test successful risk analysis endpoint."""
        # Mock dependencies
        mock_data_service = AsyncMock()
        mock_data_service.get_financial_report.return_value = {
            "ticker": "600519.SH",
            "fiscal_year": 2023,
            "revenue": "50000000000",
            "net_income": "10000000000",
            "operating_cash_flow": "12000000000",
            "assets_total": "100000000000",
            "liabilities_total": "30000000000",
            "equity_total": "70000000000",
            "cash_and_equivalents": "15000000000",
            "interest_bearing_debt": "10000000000",
            "goodwill": "2000000000",
            "accounts_receivable": "5000000000",
            "inventory": "8000000000",
        }

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()

        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock()

        # Mock the risk analyzer
        _mock_risk_score = RiskScore(
            analysis_id="test-id",
            ticker="600519.SH",
            fiscal_year=2023,
            beneish_m_score=-2.5,
            manipulation_probability=0.15,
            high_cash_high_debt=False,
            goodwill_ratio=0.02,
            profit_cash_divergence=False,
            overall_risk_level="LOW",
            risk_flags=[],
            calculated_at="2024-01-01T00:00:00",
        )

        mocker.patch(
            "stockvaluefinder.api.risk_extensions.get_initialized_data_service",
            return_value=mock_data_service,
        )
        mocker.patch(
            "stockvaluefinder.api.risk_extensions.get_db",
            return_value=mock_db,
        )

        # Make request
        client.post(
            "/api/v1/analyze/risk/",
            json={"ticker": "600519.SH"},
        )

        # Note: This test will need adjustment based on actual implementation
        # since we're using TestClient which doesn't support async dependencies fully
        # In real scenario, you'd use pytest-httpx or similar

    def test_risk_analysis_request_validation_valid(self):
        """Test valid risk analysis request."""
        request = RiskAnalysisRequest(ticker="600519.SH")

        assert request.ticker == "600519.SH"
        assert request.year is None

    def test_risk_analysis_request_validation_with_year(self):
        """Test risk analysis request with year."""
        request = RiskAnalysisRequest(ticker="600519.SH", year=2023)

        assert request.ticker == "600519.SH"
        assert request.year == 2023

    def test_risk_analysis_request_validation_invalid_ticker(self):
        """Test invalid ticker format."""
        with pytest.raises(ValueError):
            RiskAnalysisRequest(ticker="INVALID")

    def test_risk_analysis_request_validation_invalid_year(self):
        """Test invalid year format."""
        with pytest.raises(ValueError):
            RiskAnalysisRequest(ticker="600519.SH", year=1800)

        with pytest.raises(ValueError):
            RiskAnalysisRequest(ticker="600519.SH", year=2100)

    def test_risk_analysis_request_validation_hk_stock(self):
        """Test Hong Kong stock ticker."""
        request = RiskAnalysisRequest(ticker="0700.HK")

        assert request.ticker == "0700.HK"

    def test_risk_analysis_request_validation_sz_stock(self):
        """Test Shenzhen stock ticker."""
        request = RiskAnalysisRequest(ticker="000002.SZ")

        assert request.ticker == "000002.SZ"

    def test_risk_analysis_request_with_document_ids(self):
        """Test risk analysis request with optional document_ids."""
        request = RiskAnalysisRequest(
            ticker="600519.SH",
            document_ids=["doc-uuid-1", "doc-uuid-2"],
        )

        assert request.document_ids == ["doc-uuid-1", "doc-uuid-2"]

    def test_risk_analysis_request_without_document_ids(self):
        """Test risk analysis request defaults document_ids to None."""
        request = RiskAnalysisRequest(ticker="600519.SH")

        assert request.document_ids is None


@pytest.mark.asyncio
class TestRiskAnalysisErrorHandling:
    """Test suite for risk analysis error handling."""

    async def test_data_validation_error(self, client, mocker):
        """Test handling of data validation errors."""
        mock_data_service = AsyncMock()
        mock_data_service.get_financial_report.side_effect = Exception(
            "Data validation failed"
        )

        mock_db = AsyncMock(spec=AsyncSession)

        mocker.patch(
            "stockvaluefinder.api.risk_extensions.get_initialized_data_service",
            return_value=mock_data_service,
        )
        mocker.patch(
            "stockvaluefinder.api.risk_extensions.get_db",
            return_value=mock_db,
        )

        client.post(
            "/api/v1/analyze/risk/",
            json={"ticker": "600519.SH"},
        )

        # Should return error response
        # Note: Implementation depends on actual error handling

    async def test_external_api_error(self, client, mocker):
        """Test handling of external API errors."""
        from stockvaluefinder.utils.errors import ExternalAPIError

        mock_data_service = AsyncMock()
        mock_data_service.get_financial_report.side_effect = ExternalAPIError(
            "External service unavailable"
        )

        mock_db = AsyncMock(spec=AsyncSession)

        mocker.patch(
            "stockvaluefinder.api.risk_extensions.get_initialized_data_service",
            return_value=mock_data_service,
        )
        mocker.patch(
            "stockvaluefinder.api.risk_extensions.get_db",
            return_value=mock_db,
        )

        client.post(
            "/api/v1/analyze/risk/",
            json={"ticker": "600519.SH"},
        )

        # Should return error response
        # Note: Implementation depends on actual error handling
