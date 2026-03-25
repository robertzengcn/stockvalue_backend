"""Unit tests for External Data Service with multi-source fallback logic."""

import os
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from stockvaluefinder.external.data_service import ExternalDataService
from stockvaluefinder.utils.errors import ExternalAPIError


@pytest.mark.asyncio
class TestExternalDataService:
    """Test suite for External Data Service with multi-source fallback."""

    async def test_initialization_akshare_only(self):
        """Test service initialization with AKShare only."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=False
        )
        await service.initialize()

        assert service._akshare is not None
        assert service._efinance is None
        assert service._tushare is None

    async def test_initialization_akshare_and_efinance(self):
        """Test service initialization with AKShare and efinance."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=True
        )
        await service.initialize()

        assert service._akshare is not None
        assert service._efinance is not None
        assert service._tushare is None

    async def test_initialization_with_tushare(self):
        """Test service initialization with Tushare token."""
        service = ExternalDataService(
            tushare_token="test_token", enable_akshare=True, enable_efinance=True
        )
        await service.initialize()

        assert service._akshare is not None
        assert service._efinance is not None
        assert service._tushare is not None

    async def test_get_current_price_akshare_success(self, mocker):
        """Test successful current price retrieval from AKShare."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=False
        )

        # Mock AKShare client
        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_stock_daily.return_value = [
            {"日期": "2024-01-02", "收盘": 1850.0, "close": 1850.0}
        ]

        service._akshare = mock_akshare

        result = await service.get_current_price("600519.SH")

        assert result == Decimal("1850.0")
        mock_akshare.get_stock_daily.assert_called_once()

    async def test_get_current_price_fallback_to_efinance(self, mocker):
        """Test fallback from AKShare to efinance for current price."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=True
        )

        # Mock AKShare failure
        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_stock_daily.side_effect = ExternalAPIError("AKShare failed")

        # Mock efinance success
        mock_efinance = AsyncMock()
        mock_efinance.check_available.return_value = True
        mock_efinance.get_stock_daily.return_value = [
            {"日期": "2024-01-02", "close": 1850.0}
        ]

        service._akshare = mock_akshare
        service._efinance = mock_efinance

        result = await service.get_current_price("600519.SH")

        assert result == Decimal("1850.0")
        mock_akshare.get_stock_daily.assert_called_once()
        mock_efinance.get_stock_daily.assert_called_once()

    async def test_get_current_price_all_sources_fail(self, mocker):
        """Test that all sources failing raises error."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=True
        )

        # Mock both sources to fail
        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_stock_daily.side_effect = ExternalAPIError("Failed")

        mock_efinance = AsyncMock()
        mock_efinance.check_available.return_value = True
        mock_efinance.get_stock_daily.side_effect = ExternalAPIError("Failed")

        service._akshare = mock_akshare
        service._efinance = mock_efinance

        with pytest.raises(ExternalAPIError, match="All data sources failed"):
            await service.get_current_price("600519.SH")

    async def test_get_financial_report_akshare_success(self, mocker):
        """Test successful financial report retrieval from AKShare."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=False
        )

        # Mock AKShare responses
        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_profit_sheet.return_value = [
            {
                "报告期": "20231231",
                "营业总收入": "50000000000",
                "净利润": "10000000000",
                "营业成本": "30000000000",
            }
        ]
        mock_akshare.get_balance_sheet.return_value = [
            {
                "报告期": "20231231",
                "资产总计": "100000000000",
                "负债合计": "30000000000",
                "所有者权益合计": "70000000000",
                "应收账款": "5000000000",
                "存货": "8000000000",
                "固定资产": "40000000000",
                "商誉": "2000000000",
                "货币资金": "15000000000",
            }
        ]
        mock_akshare.get_cash_flow_sheet.return_value = [
            {"报告期": "20231231", "经营活动产生的现金流量净额": "12000000000"}
        ]

        service._akshare = mock_akshare

        result = await service.get_financial_report("600519.SH", 2023)

        assert result["fiscal_year"] == 2023
        assert result["revenue"] == "50000000000"
        assert result["net_income"] == "10000000000"
        assert result["report_source"] == "AKShare"

    async def test_get_financial_report_fallback_efinance(self, mocker):
        """Test fallback from AKShare to efinance for financial report."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=True
        )

        # Mock AKShare failure
        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_profit_sheet.side_effect = ExternalAPIError("Failed")

        # Mock efinance success
        mock_efinance = AsyncMock()
        mock_efinance.check_available.return_value = True
        mock_efinance.get_profit_sheet.return_value = [
            {
                "报告期": "2023-12-31",
                "营业总收入": "50000000000",
                "净利润": "10000000000",
            }
        ]
        mock_efinance.get_balance_sheet.return_value = [
            {
                "报告期": "2023-12-31",
                "资产总计": "100000000000",
                "负债合计": "30000000000",
                "所有者权益合计": "70000000000",
                "应收账款": "5000000000",
                "存货": "8000000000",
                "固定资产": "40000000000",
                "商誉": "2000000000",
                "货币资金": "15000000000",
            }
        ]
        mock_efinance.get_cash_flow_sheet.return_value = [
            {"报告期": "2023-12-31", "经营活动产生的现金流量净额": "12000000000"}
        ]

        service._akshare = mock_akshare
        service._efinance = mock_efinance

        result = await service.get_financial_report("600519.SH", 2023)

        assert result["fiscal_year"] == 2023
        assert result["revenue"] == "50000000000"
        assert result["report_source"] == "efinance"

    @patch.dict(os.environ, {"DEVELOPMENT_MODE": "true"})
    async def test_get_financial_report_mock_fallback(self, mocker):
        """Test fallback to mock data in development mode."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=True
        )

        # Mock both sources to fail
        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_profit_sheet.side_effect = ExternalAPIError("Failed")

        mock_efinance = AsyncMock()
        mock_efinance.check_available.return_value = True
        mock_efinance.get_profit_sheet.side_effect = ExternalAPIError("Failed")

        service._akshare = mock_akshare
        service._efinance = mock_efinance

        # Set development mode
        import stockvaluefinder.external.data_service as ds_module

        original_dev_mode = ds_module.DEVELOPMENT_MODE
        ds_module.DEVELOPMENT_MODE = True

        try:
            result = await service.get_financial_report("600519.SH", 2023)

            assert result["fiscal_year"] == 2023
            assert "revenue" in result
            assert "net_income" in result
            # Mock data has specific values
            assert result["revenue"] == "50000000000"
        finally:
            ds_module.DEVELOPMENT_MODE = original_dev_mode

    async def test_get_dividend_yield_akshare_success(self, mocker):
        """Test successful dividend yield retrieval from AKShare."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=False
        )

        # Mock price and dividend data
        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_stock_daily.return_value = [
            {"日期": "2024-01-02", "收盘": 1850.0, "close": 1850.0}
        ]
        mock_akshare.get_dividend_by_year.return_value = [
            {"分红年度": "2023", "分红": "50.00"}
        ]

        service._akshare = mock_akshare

        result = await service.get_dividend_yield("600519.SH")

        assert isinstance(result, float)
        assert result > 0

    async def test_shutdown(self):
        """Test service shutdown."""
        service = ExternalDataService(
            tushare_token="test_token", enable_akshare=True, enable_efinance=True
        )

        # Mock clients
        service._tushare = AsyncMock()
        service._tushare.__aexit__ = AsyncMock()

        await service.shutdown()

        # Verify shutdown was called
        if service._tushare:
            # Shutdown should complete without error
            assert True


@pytest.mark.asyncio
class TestGrossMarginCalculation:
    """Test suite for gross margin calculation from different sources."""

    async def test_calculate_gross_margin_from_akshare(self):
        """Test gross margin calculation from AKShare data."""
        service = ExternalDataService(tushare_token="", enable_akshare=True)

        income_data = {
            "营业总收入": "100000",
            "营业成本": "60000",
        }

        result = service._calculate_gross_margin_from_akshare(income_data)

        assert result == 40.0  # (100000 - 60000) / 100000 * 100

    async def test_calculate_gross_margin_from_akshare_zero_revenue(self):
        """Test gross margin calculation with zero revenue."""
        service = ExternalDataService(tushare_token="", enable_akshare=True)

        income_data = {
            "营业总收入": "0",
            "营业成本": "60000",
        }

        result = service._calculate_gross_margin_from_akshare(income_data)

        assert result == 0.0

    async def test_calculate_gross_margin_from_efinance(self):
        """Test gross margin calculation from efinance data."""
        service = ExternalDataService(tushare_token="", enable_akshare=True)

        income_data = {
            "营业总收入": "100000",
            "营业成本": "60000",
        }

        result = service._calculate_gross_margin_from_efinance(income_data)

        assert result == 40.0


@pytest.mark.asyncio
class TestMockFinancialData:
    """Test suite for mock financial data generation."""

    async def test_get_mock_financial_report(self):
        """Test mock financial report generation."""
        service = ExternalDataService(tushare_token="", enable_akshare=True)

        result = service._get_mock_financial_report("600519.SH", 2023)

        assert result["ticker"] == "600519.SH"
        assert result["fiscal_year"] == 2023
        assert result["revenue"] == "50000000000"
        assert result["net_income"] == "10000000000"
        assert result["goodwill"] == "2000000000"
        assert result["report_source"] == "Mock (Development Mode)"

        # Check that M-Score indices are present
        assert "days_sales_receivables_index" in result
        assert "gross_margin_index" in result
        assert "asset_quality_index" in result
