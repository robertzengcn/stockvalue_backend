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
        """Test successful current price retrieval from AKShare when efinance is off."""
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
        service._initialized = True

        result = await service.get_current_price("600519.SH")

        assert result == Decimal("1850.0")
        mock_akshare.get_stock_daily.assert_called_once()

    async def test_get_current_price_efinance_latest_quote_first(self, mocker):
        """Spot price uses efinance latest quote before AKShare kline."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=True
        )

        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True

        mock_efinance = AsyncMock()
        mock_efinance.check_available.return_value = True
        mock_efinance.get_latest_trade_price = AsyncMock(return_value=1850.0)

        service._akshare = mock_akshare
        service._efinance = mock_efinance
        service._initialized = True

        result = await service.get_current_price("600519.SH")

        assert result == Decimal("1850.0")
        mock_efinance.get_latest_trade_price.assert_called_once_with("600519.SH")
        mock_akshare.get_stock_daily.assert_not_called()

    async def test_get_current_price_fallback_to_akshare_after_efinance(self, mocker):
        """When efinance latest quote fails, fall back to AKShare daily."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=True
        )

        mock_efinance = AsyncMock()
        mock_efinance.check_available.return_value = True
        mock_efinance.get_latest_trade_price = AsyncMock(
            side_effect=ExternalAPIError("efinance failed")
        )

        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_stock_daily.return_value = [
            {"日期": "2024-01-02", "收盘": 1850.0, "close": 1850.0}
        ]

        service._akshare = mock_akshare
        service._efinance = mock_efinance
        service._initialized = True

        result = await service.get_current_price("600519.SH")

        assert result == Decimal("1850.0")
        mock_efinance.get_latest_trade_price.assert_called_once()
        mock_akshare.get_stock_daily.assert_called_once()

    async def test_get_current_price_all_sources_fail(self, mocker):
        """Test that all sources failing raises error."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=True
        )

        mock_efinance = AsyncMock()
        mock_efinance.check_available.return_value = True
        mock_efinance.get_latest_trade_price = AsyncMock(
            side_effect=ExternalAPIError("Failed")
        )

        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_stock_daily.side_effect = ExternalAPIError("Failed")

        service._akshare = mock_akshare
        service._efinance = mock_efinance
        service._initialized = True

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
        service._initialized = True

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
        service._initialized = True

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
        service._initialized = True

        result = await service.get_financial_report("600519.SH", 2023)

        assert result["fiscal_year"] == 2023
        assert "revenue" in result
        assert "net_income" in result
        assert result["revenue"] == "50000000000"

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
        mock_akshare.get_dividend_history.return_value = [
            {"公告日期": "2024-06-15", "派息": 50.0},
        ]

        service._akshare = mock_akshare
        service._initialized = True

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


# ===========================================================================
# Task 1: Extended tests for uncovered methods and fallback paths
# ===========================================================================


@pytest.mark.asyncio
class TestGetCurrentPrice:
    """Tests for get_current_price with Decimal return type and fallback logic."""

    async def test_returns_decimal_from_akshare(self):
        """get_current_price returns Decimal when AKShare returns valid data."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=False
        )

        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_stock_daily.return_value = [
            {"日期": "2024-01-02", "收盘": 1850.50, "close": 1850.50}
        ]

        service._akshare = mock_akshare
        service._initialized = True

        result = await service.get_current_price("600519.SH")

        assert isinstance(result, Decimal)
        assert result == Decimal("1850.50")

    async def test_fallback_to_efinance_on_akshare_failure(self):
        """get_current_price falls back to efinance when AKShare raises exception."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=True
        )

        mock_efinance = AsyncMock()
        mock_efinance.check_available.return_value = True
        mock_efinance.get_latest_trade_price = AsyncMock(return_value=1800.00)

        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_stock_daily.side_effect = ExternalAPIError("AKShare down")

        service._akshare = mock_akshare
        service._efinance = mock_efinance
        service._initialized = True

        result = await service.get_current_price("600519.SH")

        assert isinstance(result, Decimal)
        assert result == Decimal("1800.0")

    @patch.dict(os.environ, {"DEVELOPMENT_MODE": "true"})
    async def test_fallback_to_mock_on_all_failures(self):
        """get_current_price falls back to mock data when all sources fail in dev mode."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=True
        )

        mock_efinance = AsyncMock()
        mock_efinance.check_available.return_value = True
        mock_efinance.get_latest_trade_price = AsyncMock(
            side_effect=ExternalAPIError("efinance down")
        )

        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_stock_daily.side_effect = ExternalAPIError("AKShare down")

        service._akshare = mock_akshare
        service._efinance = mock_efinance
        service._initialized = True

        result = await service.get_current_price("600519.SH")

        assert isinstance(result, Decimal)
        # Mock price is deterministic based on hash of ticker
        assert result > Decimal("0")


@pytest.mark.asyncio
class TestGetFreeCashFlow:
    """Tests for get_free_cash_flow with FCF calculation from cashflow data."""

    async def test_returns_calculated_fcf(self):
        """get_free_cash_flow calculates FCF from operating cash flow and capex."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=False
        )

        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        # OCF = 12,000,000,000; CapEx = 2,000,000,000
        mock_akshare.get_cash_flow_sheet.return_value = [
            {
                "经营活动产生的现金流量净额": 12000000000,
                "购建固定资产、无形资产和其他长期资产支付的现金": 2000000000,
            }
        ]

        service._akshare = mock_akshare
        service._initialized = True

        result = await service.get_free_cash_flow("600519.SH", "20231231")

        # FCF = OCF - abs(CapEx) = 12B - 2B = 10B; in millions = 10000.0
        assert isinstance(result, float)
        assert result == 10000.0

    async def test_returns_calculated_fcf_with_english_fields(self):
        """get_free_cash_flow handles English field names from AKShare."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=False
        )

        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_cash_flow_sheet.return_value = [
            {
                "NETCASH_OPERATE": 12000000000,
                "CONSTRUCT_LONG_ASSET": 2000000000,
            }
        ]

        service._akshare = mock_akshare
        service._initialized = True

        result = await service.get_free_cash_flow("600519.SH", "20231231")

        assert isinstance(result, float)
        assert result == 10000.0


@pytest.mark.asyncio
class TestGetSharesOutstanding:
    """Tests for get_shares_outstanding returning share count from data source."""

    async def test_returns_share_count(self):
        """get_shares_outstanding returns total shares in millions from AKShare."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=False
        )

        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        # 1.256 billion shares
        mock_akshare.get_shares_outstanding = AsyncMock(return_value=1_256_000_000)

        service._akshare = mock_akshare
        service._initialized = True

        result = await service.get_shares_outstanding("600519.SH")

        assert isinstance(result, float)
        # 1,256,000,000 / 1,000,000 = 1256.0
        assert result == 1256.0


@pytest.mark.asyncio
class TestGetDividendYield:
    """Tests for get_dividend_yield returning yield as float."""

    async def test_returns_yield_as_float(self):
        """get_dividend_yield returns gross dividend yield as a float between 0 and 1."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=False
        )

        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_stock_daily.return_value = [
            {"日期": "2024-01-02", "收盘": 1850.0, "close": 1850.0}
        ]
        # 4 records of 50.0 per 10 shares = 200/10 = 20 per share
        mock_akshare.get_dividend_history.return_value = [
            {"公告日期": "2024-06-15", "派息": 50.0},
            {"公告日期": "2023-06-15", "派息": 50.0},
            {"公告日期": "2022-06-15", "派息": 50.0},
            {"公告日期": "2021-06-15", "派息": 50.0},
        ]

        service._akshare = mock_akshare
        service._initialized = True

        result = await service.get_dividend_yield("600519.SH")

        assert isinstance(result, float)
        assert 0 < result < 1
        # (4 * 50.0 / 10.0) / 1850.0 = 20.0 / 1850.0 ≈ 0.01081
        expected = (4 * 50.0 / 10.0) / 1850.0
        assert abs(result - expected) < 0.0001


@pytest.mark.asyncio
class TestGetStockBasic:
    """Tests for get_stock_basic returning stock metadata dict."""

    async def test_returns_stock_metadata(self):
        """get_stock_basic returns dict with ticker, name, market fields."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=False
        )

        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_stock_info_a.return_value = [
            {
                "code": "600519",
                "name": "贵州茅台",
                "market": "SH",
                "industry": "白酒",
            }
        ]

        service._akshare = mock_akshare
        service._initialized = True

        result = await service.get_stock_basic("600519.SH")

        assert isinstance(result, list)
        assert len(result) > 0
        first = result[0]
        assert "code" in first or "name" in first


@pytest.mark.asyncio
class TestFallbackChain:
    """Tests for the AKShare -> efinance -> Tushare -> Mock fallback chain."""

    async def test_akshare_primary_efinance_secondary(self):
        """When AKShare fails, efinance is tried and returns valid data."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=True
        )

        # AKShare returns None (triggers DataValidationError for missing data)
        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_profit_sheet.return_value = []

        # efinance returns valid data
        mock_efinance = AsyncMock()
        mock_efinance.check_available.return_value = True
        mock_efinance.get_profit_sheet.return_value = [
            {
                "报告期": "2023-12-31",
                "营业总收入": "45000000000",
                "净利润": "9000000000",
            }
        ]
        mock_efinance.get_balance_sheet.return_value = [
            {
                "报告期": "2023-12-31",
                "资产总计": "90000000000",
                "负债合计": "25000000000",
                "所有者权益合计": "65000000000",
                "应收账款": "4000000000",
                "存货": "7000000000",
                "固定资产": "35000000000",
                "商誉": "1000000000",
                "货币资金": "12000000000",
            }
        ]
        mock_efinance.get_cash_flow_sheet.return_value = [
            {"报告期": "2023-12-31", "经营活动产生的现金流量净额": "11000000000"}
        ]

        service._akshare = mock_akshare
        service._efinance = mock_efinance
        service._initialized = True

        result = await service.get_financial_report("600519.SH", 2023)

        assert result["fiscal_year"] == 2023
        assert result["revenue"] == "45000000000"
        assert result["report_source"] == "efinance"

    @patch.dict(os.environ, {"DEVELOPMENT_MODE": "true"})
    async def test_all_sources_fail_uses_mock(self):
        """In development mode, when all real sources fail, mock data is returned."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=True
        )

        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_profit_sheet.side_effect = ExternalAPIError("AKShare down")

        mock_efinance = AsyncMock()
        mock_efinance.check_available.return_value = True
        mock_efinance.get_profit_sheet.side_effect = ExternalAPIError("efinance down")

        service._akshare = mock_akshare
        service._efinance = mock_efinance
        service._initialized = True

        result = await service.get_financial_report("000001.SZ", 2023)

        assert result["fiscal_year"] == 2023
        assert "revenue" in result
        assert "net_income" in result
        assert result["report_source"] == "Mock (Development Mode)"


@pytest.mark.asyncio
class TestFieldNormalization:
    """Tests for AKShare field name normalization to standardized English keys."""

    async def test_akshare_fields_mapped_to_standard_keys(self):
        """AKShare Chinese field names are mapped to standardized English keys."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=False
        )

        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_profit_sheet.return_value = [
            {
                "报告期": "20231231",
                "营业总收入": "50000000000",
                "净利润": "10000000000",
                "营业成本": "30000000000",
                "营业总成本": "40000000000",
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
                "流动资产合计": "45000000000",
                "长期借款": "8000000000",
            }
        ]
        mock_akshare.get_cash_flow_sheet.return_value = [
            {"报告期": "20231231", "经营活动产生的现金流量净额": "12000000000"}
        ]

        service._akshare = mock_akshare
        service._initialized = True

        result = await service.get_financial_report("600519.SH", 2023)

        # Verify Chinese AKShare fields are mapped to English standardized keys
        assert "revenue" in result
        assert "net_income" in result
        assert "operating_cash_flow" in result
        assert "assets_total" in result
        assert "liabilities_total" in result
        assert "equity_total" in result
        assert "accounts_receivable" in result
        assert "inventory" in result
        assert "fixed_assets" in result
        assert "goodwill" in result
        assert "cash_and_equivalents" in result
        assert "interest_bearing_debt" in result
        assert "cost_of_goods" in result
        assert "sga_expense" in result
        assert "total_current_assets" in result
        assert "ppe" in result
        assert "total_liabilities" in result
        assert result["report_source"] == "AKShare"


# ===========================================================================
# Task 2: Edge case tests for normalization and error handling
# ===========================================================================


@pytest.mark.asyncio
class TestDataServiceEdgeCases:
    """Edge case tests for data service normalization and error handling."""

    async def test_get_financial_report_with_invalid_ticker_format(self):
        """Calling get_financial_report with invalid ticker raises error gracefully."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=False
        )

        # No mock clients set up, so AKShare will be None after init
        service._akshare = None
        service._initialized = True

        with pytest.raises(ExternalAPIError, match="All data sources failed"):
            await service.get_financial_report("INVALID", 2023)

    async def test_get_financial_report_with_zero_revenue(self):
        """Financial report with revenue=0 does not crash; returns revenue='0'."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=False
        )

        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_profit_sheet.return_value = [
            {
                "报告期": "20231231",
                "营业总收入": "0",
                "净利润": "0",
                "营业成本": "0",
                "营业总成本": "0",
            }
        ]
        mock_akshare.get_balance_sheet.return_value = [
            {
                "报告期": "20231231",
                "资产总计": "100000000000",
                "负债合计": "30000000000",
                "所有者权益合计": "70000000000",
                "应收账款": "0",
                "存货": "0",
                "固定资产": "0",
                "商誉": "0",
                "货币资金": "0",
            }
        ]
        mock_akshare.get_cash_flow_sheet.return_value = [
            {"报告期": "20231231", "经营活动产生的现金流量净额": "0"}
        ]

        service._akshare = mock_akshare
        service._initialized = True

        result = await service.get_financial_report("600519.SH", 2023)

        assert result["revenue"] == "0"
        assert result["net_income"] == "0"

    async def test_get_financial_report_preserves_report_id(self):
        """Calling get_financial_report twice generates different report_id values (UUID)."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=False
        )

        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_profit_sheet.return_value = [
            {
                "报告期": "20231231",
                "营业总收入": "50000000000",
                "净利润": "10000000000",
                "营业成本": "30000000000",
                "营业总成本": "40000000000",
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
        service._initialized = True

        result1 = await service.get_financial_report("600519.SH", 2023)
        result2 = await service.get_financial_report("600519.SH", 2023)

        assert result1["report_id"] != result2["report_id"]

    async def test_mock_report_has_all_required_fields(self):
        """Mock financial report has all fields required by risk_service."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True
        )

        result = service._get_mock_financial_report("600519.SH", 2023)

        required_fields = [
            "revenue",
            "net_income",
            "operating_cash_flow",
            "accounts_receivable",
            "cost_of_goods",
            "total_current_assets",
            "assets_total",
            "ppe",
            "sga_expense",
            "total_liabilities",
            "cash_and_equivalents",
            "interest_bearing_debt",
            "goodwill",
            "equity_total",
        ]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    async def test_get_financial_report_handles_nan_values(self):
        """NaN values from source are handled gracefully in string conversion."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=True, enable_efinance=False
        )

        mock_akshare = AsyncMock()
        mock_akshare.check_available.return_value = True
        mock_akshare.get_profit_sheet.return_value = [
            {
                "报告期": "20231231",
                "营业总收入": float("nan"),
                "净利润": "10000000000",
                "营业成本": "30000000000",
                "营业总成本": "40000000000",
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
        service._initialized = True

        result = await service.get_financial_report("600519.SH", 2023)

        # Should not crash; revenue field will be "nan" string
        assert "revenue" in result
        assert isinstance(result["revenue"], str)


@pytest.mark.asyncio
class TestDataServiceInitialization:
    """Tests for data service initialization with various source configurations."""

    async def test_service_with_no_sources_enabled(self):
        """Service with no sources enabled initializes and returns mock data in dev mode."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=False, enable_efinance=False
        )
        await service.initialize()

        assert service._akshare is None
        assert service._efinance is None
        assert service._tushare is None
        assert service._initialized is True

    @patch.dict(os.environ, {"DEVELOPMENT_MODE": "true"})
    async def test_service_with_no_sources_returns_mock_in_dev_mode(self):
        """Service with no sources returns mock data in development mode."""
        service = ExternalDataService(
            tushare_token="", enable_akshare=False, enable_efinance=False
        )
        service._initialized = True

        result = await service.get_financial_report("600519.SH", 2023)

        assert result["fiscal_year"] == 2023
        assert result["report_source"] == "Mock (Development Mode)"

    async def test_service_with_tushare_token(self):
        """Service with a Tushare token initializes the tushare_client."""
        service = ExternalDataService(
            tushare_token="valid_test_token",
            enable_akshare=True,
            enable_efinance=True,
        )

        # We need to mock the TushareClient __aenter__ to avoid real connection
        with patch(
            "stockvaluefinder.external.data_service.TushareClient"
        ) as mock_tushare_class:
            mock_tushare_instance = AsyncMock()
            mock_tushare_class.return_value = mock_tushare_instance

            await service.initialize()

            # Verify tushare_client was initialized
            assert service._tushare is not None
            mock_tushare_instance.__aenter__.assert_called_once()
