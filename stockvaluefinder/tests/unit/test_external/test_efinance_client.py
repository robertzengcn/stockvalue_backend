"""Unit tests for efinance client."""

import pytest
from datetime import date

from stockvaluefinder.external.efinance_client import (
    EFinanceClient,
    normalize_efinance_quote_code,
)
from stockvaluefinder.utils.errors import ExternalAPIError


def test_normalize_efinance_quote_code_maps_hk() -> None:
    assert normalize_efinance_quote_code("600519.SH") == "600519"
    assert normalize_efinance_quote_code("0700.HK") == "00700"


@pytest.mark.asyncio
class TestEFinanceClient:
    """Test suite for efinance client functionality."""

    async def test_check_available(self):
        """Test that efinance library availability check works."""
        client = EFinanceClient()
        available = await client.check_available()
        # Should be True since efinance is installed
        assert isinstance(available, bool)

    async def test_client_initialization(self):
        """Test client initialization with default parameters."""
        client = EFinanceClient()
        assert client.timeout == 30.0
        assert client.max_retries == 3
        assert not client._available  # Not checked yet

    async def test_client_initialization_custom_params(self):
        """Test client initialization with custom parameters."""
        client = EFinanceClient(timeout=60.0, max_retries=5)
        assert client.timeout == 60.0
        assert client.max_retries == 5

    async def test_get_stock_base_info_success(self, mocker):
        """Test successful stock basic info retrieval."""
        mock_ef = mocker.MagicMock()
        mock_df = mocker.MagicMock()
        mock_df.empty = False
        mock_df.iloc.__getitem__.return_value.to_dict.return_value = {
            "股票代码": "600519",
            "股票名称": "贵州茅台",
            "行业": "白酒",
        }

        mock_ef.stock.get_base_info.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"efinance": mock_ef})

        client = EFinanceClient()
        await client.check_available()

        result = await client.get_stock_base_info("600519")

        assert isinstance(result, dict)
        assert len(result) > 0

    async def test_get_stock_base_info_empty(self, mocker):
        """Test handling of empty stock info response."""
        mock_ef = mocker.MagicMock()
        mock_df = mocker.MagicMock()
        mock_df.empty = True
        mock_ef.stock.get_base_info.return_value = mock_df

        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"efinance": mock_ef})

        client = EFinanceClient()
        await client.check_available()

        result = await client.get_stock_base_info("600519")

        assert result == {}

    async def test_get_stock_daily_success(self, mocker):
        """Test successful daily market data retrieval."""
        mock_ef = mocker.MagicMock()
        mock_df = mocker.MagicMock()
        mock_df.to_dict.return_value = [
            {
                "股票代码": "600519",
                "日期": "2024-01-02",
                "开盘": 1800.0,
                "收盘": 1850.0,
                "最高": 1860.0,
                "最低": 1790.0,
                "成交量": 1000000,
            }
        ]

        mock_ef.stock.get_quote_history.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"efinance": mock_ef})

        client = EFinanceClient()
        await client.check_available()

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 10)
        result = await client.get_stock_daily("600519", start_date, end_date)

        assert isinstance(result, list)

    async def test_get_profit_sheet_success(self, mocker):
        """Test successful profit sheet retrieval."""
        mock_ef = mocker.MagicMock()
        mock_df = mocker.MagicMock()
        mock_df.to_dict.return_value = [
            {
                "股票代码": "600519",
                "报告期": "2023-12-31",
                "营业总收入": 50000000000,
                "净利润": 10000000000,
            }
        ]

        mock_ef.stock.get_profit_sheet.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"efinance": mock_ef})

        client = EFinanceClient()
        await client.check_available()

        result = await client.get_profit_sheet("600519", "20231231")

        assert isinstance(result, list)

    async def test_get_balance_sheet_success(self, mocker):
        """Test successful balance sheet retrieval."""
        mock_ef = mocker.MagicMock()
        mock_df = mocker.MagicMock()
        mock_df.to_dict.return_value = [
            {
                "股票代码": "600519",
                "报告期": "2023-12-31",
                "资产总计": 100000000000,
                "负债合计": 30000000000,
            }
        ]

        mock_ef.stock.get_balance_sheet.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"efinance": mock_ef})

        client = EFinanceClient()
        await client.check_available()

        result = await client.get_balance_sheet("600519", "20231231")

        assert isinstance(result, list)

    async def test_get_cash_flow_sheet_success(self, mocker):
        """Test successful cash flow statement retrieval."""
        mock_ef = mocker.MagicMock()
        mock_df = mocker.MagicMock()
        mock_df.to_dict.return_value = [
            {
                "股票代码": "600519",
                "报告期": "2023-12-31",
                "经营活动产生的现金流量净额": 12000000000,
            }
        ]

        mock_ef.stock.get_cash_flow_sheet.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"efinance": mock_ef})

        client = EFinanceClient()
        await client.check_available()

        result = await client.get_cash_flow_sheet("600519", "20231231")

        assert isinstance(result, list)

    async def test_get_latest_trade_price_success(self, mocker):
        """Latest price from get_latest_quote (not kline)."""
        mock_ef = mocker.MagicMock()
        mock_df = mocker.MagicMock()
        mock_df.empty = False
        mock_row = mocker.MagicMock()
        mock_row.get.side_effect = lambda k, d=None: (
            1401.18 if k == "最新价" else d
        )
        mock_df.iloc.__getitem__.return_value = mock_row
        mock_ef.stock.get_latest_quote.return_value = mock_df

        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"efinance": mock_ef})

        client = EFinanceClient()
        await client.check_available()

        price = await client.get_latest_trade_price("600519.SH")
        assert price == 1401.18
        mock_ef.stock.get_latest_quote.assert_called_once_with("600519")

    async def test_get_realtime_quotes_success(self, mocker):
        """Test successful real-time quotes retrieval."""
        mock_ef = mocker.MagicMock()
        mock_df = mocker.MagicMock()
        mock_df.to_dict.return_value = [
            {
                "股票代码": "600519",
                "最新价": 1850.0,
                "涨跌幅": 1.5,
            },
            {
                "股票代码": "000001",
                "最新价": 10.5,
                "涨跌幅": -0.5,
            },
        ]

        mock_ef.stock.get_realtime_quotes.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"efinance": mock_ef})

        client = EFinanceClient()
        await client.check_available()

        result = await client.get_realtime_quotes(["600519", "000001"])

        assert isinstance(result, list)
        assert len(result) == 2

    async def test_unavailable_library_raises_error(self):
        """Test that unavailable library raises appropriate error."""
        client = EFinanceClient()
        client._available = False

        with pytest.raises(ExternalAPIError, match="efinance library is not available"):
            await client.get_stock_base_info("600519")

    async def test_retry_on_failure(self, mocker):
        """Test that client retries on failure."""
        mock_ef = mocker.MagicMock()
        mock_ef.stock.get_base_info.side_effect = Exception("Network error")

        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"efinance": mock_ef})

        client = EFinanceClient(timeout=1.0, max_retries=2)
        await client.check_available()

        with pytest.raises(ExternalAPIError, match="failed after 2 attempts"):
            await client.get_stock_base_info("600519")

        assert mock_ef.stock.get_base_info.call_count == 2
