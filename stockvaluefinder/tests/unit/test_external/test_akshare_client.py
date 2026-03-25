"""Unit tests for AKShare client."""

import pytest
from datetime import date

from stockvaluefinder.external.akshare_client import AKShareClient
from stockvaluefinder.utils.errors import ExternalAPIError


@pytest.mark.asyncio
class TestAKShareClient:
    """Test suite for AKShare client functionality."""

    async def test_check_available(self):
        """Test that AKShare library availability check works."""
        client = AKShareClient()
        available = await client.check_available()
        # Should be True since akshare is installed
        assert isinstance(available, bool)

    async def test_client_initialization(self):
        """Test client initialization with default parameters."""
        client = AKShareClient()
        assert client.timeout == 30.0
        assert client.max_retries == 3
        assert not client._available  # Not checked yet

    async def test_client_initialization_custom_params(self):
        """Test client initialization with custom parameters."""
        client = AKShareClient(timeout=60.0, max_retries=5)
        assert client.timeout == 60.0
        assert client.max_retries == 5

    async def test_get_stock_info_a_success(self, mocker):
        """Test successful A-share stock info retrieval."""
        # Mock akshare import and function
        mock_ak = mocker.MagicMock()
        mock_df = mocker.MagicMock()
        mock_df.to_dict.return_value = [{"symbol": "600519", "name": "贵州茅台"}]

        mock_ak.stock_individual_info_em.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        result = await client.get_stock_info_a("600519")

        assert isinstance(result, list)
        assert len(result) > 0
        assert "symbol" in result[0] or "股票代码" in result[0]

    async def test_get_stock_daily_success(self, mocker):
        """Test successful daily market data retrieval."""
        mock_ak = mocker.MagicMock()
        mock_df = mocker.MagicMock()
        mock_df.to_dict.return_value = [
            {
                "日期": "2024-01-02",
                "开盘": 1800.0,
                "收盘": 1850.0,
                "最高": 1860.0,
                "最低": 1790.0,
                "成交量": 1000000,
            }
        ]

        mock_ak.stock_zh_a_hist.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 10)
        result = await client.get_stock_daily("600519", start_date, end_date)

        assert isinstance(result, list)
        assert len(result) > 0

    async def test_get_profit_sheet_success(self, mocker):
        """Test successful profit sheet (income statement) retrieval."""
        mock_ak = mocker.MagicMock()
        mock_df = mocker.MagicMock()
        mock_df.to_dict.return_value = [
            {
                "报告期": "20231231",
                "营业总收入": 50000000000,
                "净利润": 10000000000,
                "营业成本": 30000000000,
            }
        ]

        mock_ak.stock_profit_sheet_by_report_em.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        result = await client.get_profit_sheet("600519", "20231231")

        assert isinstance(result, list)
        assert len(result) > 0

    async def test_get_balance_sheet_success(self, mocker):
        """Test successful balance sheet retrieval."""
        mock_ak = mocker.MagicMock()
        mock_df = mocker.MagicMock()
        mock_df.to_dict.return_value = [
            {
                "报告期": "20231231",
                "资产总计": 100000000000,
                "负债合计": 30000000000,
                "所有者权益合计": 70000000000,
            }
        ]

        mock_ak.stock_balance_sheet_by_report_em.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        result = await client.get_balance_sheet("600519", "20231231")

        assert isinstance(result, list)
        assert len(result) > 0

    async def test_get_cash_flow_sheet_success(self, mocker):
        """Test successful cash flow statement retrieval."""
        mock_ak = mocker.MagicMock()
        mock_df = mocker.MagicMock()
        mock_df.to_dict.return_value = [
            {
                "报告期": "20231231",
                "经营活动产生的现金流量净额": 12000000000,
                "投资活动产生的现金流量净额": -5000000000,
            }
        ]

        mock_ak.stock_cash_flow_sheet_by_report_em.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        result = await client.get_cash_flow_sheet("600519", "20231231")

        assert isinstance(result, list)
        assert len(result) > 0

    async def test_get_dividend_by_year_success(self, mocker):
        """Test successful dividend data retrieval."""
        mock_ak = mocker.MagicMock()
        mock_df = mocker.MagicMock()
        mock_df.to_dict.return_value = [
            {"分红年度": "2023", "分红": "50.00", "除权除息日": "2024-06-30"}
        ]

        mock_ak.stock_dividend_by_year.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        result = await client.get_dividend_by_year("600519", 2023)

        assert isinstance(result, list)
        assert len(result) > 0

    async def test_unavailable_library_raises_error(self):
        """Test that unavailable library raises appropriate error."""
        client = AKShareClient()
        client._available = False  # Simulate unavailable library

        with pytest.raises(ExternalAPIError, match="AKShare library is not available"):
            await client.get_stock_info_a("600519")

    async def test_retry_on_failure(self, mocker):
        """Test that client retries on failure."""
        mock_ak = mocker.MagicMock()
        mock_ak.stock_individual_info_em.side_effect = Exception("Network error")

        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient(timeout=1.0, max_retries=2)
        await client.check_available()

        with pytest.raises(ExternalAPIError, match="failed after 2 attempts"):
            await client.get_stock_info_a("600519")

        # Should have been called max_retries times
        assert mock_ak.stock_individual_info_em.call_count == 2
