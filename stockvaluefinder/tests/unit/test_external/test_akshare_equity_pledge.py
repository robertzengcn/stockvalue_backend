"""Unit tests for AKShare client equity pledge methods."""

import pandas as pd  # type: ignore[import-untyped]
import pytest

from stockvaluefinder.external.akshare_client import AKShareClient


@pytest.mark.asyncio
class TestEquityPledgeRatioByDate:
    """Tests for get_equity_pledge_ratio_by_date."""

    async def test_returns_list_of_dicts_with_chinese_field_names(self, mocker) -> None:
        """Should return list of dicts with Chinese field names from AKShare."""
        mock_ak = mocker.MagicMock()
        mock_df = pd.DataFrame(
            [
                {
                    "股票代码": "600519",
                    "股票简称": "贵州茅台",
                    "交易日期": "2024-06-05",
                    "所属行业": "白酒",
                    "质押比例": 35.5,
                    "质押股数": 100000,
                    "质押市值": 50000000,
                    "质押笔数": 10,
                    "无限售股质押数": 80000,
                    "限售股质押数": 20000,
                    "近一年涨跌幅": -5.2,
                }
            ]
        )

        mock_ak.stock_gpzy_pledge_ratio_em.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        result = await client.get_equity_pledge_ratio_by_date("20240605")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["股票代码"] == "600519"
        assert result[0]["质押比例"] == 35.5

    async def test_passes_date_param_correctly(self, mocker) -> None:
        """Should pass the trade_date parameter to AKShare function."""
        mock_ak = mocker.MagicMock()
        mock_df = pd.DataFrame([{"股票代码": "600519", "质押比例": 35.5}])

        mock_ak.stock_gpzy_pledge_ratio_em.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        await client.get_equity_pledge_ratio_by_date("20240605")

        mock_ak.stock_gpzy_pledge_ratio_em.assert_called_once_with(date="20240605")

    async def test_empty_dataframe_returns_empty_list(self, mocker) -> None:
        """Empty DataFrame should return empty list."""
        mock_ak = mocker.MagicMock()
        mock_ak.stock_gpzy_pledge_ratio_em.return_value = pd.DataFrame()
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        result = await client.get_equity_pledge_ratio_by_date("20240605")

        assert result == []

    async def test_none_dataframe_returns_empty_list(self, mocker) -> None:
        """None DataFrame should return empty list."""
        mock_ak = mocker.MagicMock()
        mock_ak.stock_gpzy_pledge_ratio_em.return_value = None
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        result = await client.get_equity_pledge_ratio_by_date("20240605")

        assert result == []


@pytest.mark.asyncio
class TestEquityPledgeRatioDetail:
    """Tests for get_equity_pledge_ratio_detail."""

    async def test_returns_list_of_dicts(self, mocker) -> None:
        """Should return list of dicts from AKShare."""
        mock_ak = mocker.MagicMock()
        mock_df = pd.DataFrame(
            [
                {
                    "股票代码": "600519",
                    "股票简称": "贵州茅台",
                    "股东名称": "XX投资公司",
                    "质押股份数量": 1000000,
                    "占所持股份比例": 50.0,
                    "占总股本比例": 5.0,
                    "质押机构": "XX证券",
                    "最新价": 1800.0,
                    "质押日收盘价": 1750.0,
                    "预估平仓线": 1200.0,
                    "质押开始日期": "2024-01-15",
                    "公告日期": "2024-01-16",
                }
            ]
        )
        mock_ak.stock_gpzy_pledge_ratio_detail_em.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        result = await client.get_equity_pledge_ratio_detail()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["股票代码"] == "600519"
        assert result[0]["股东名称"] == "XX投资公司"

    async def test_empty_dataframe_returns_empty_list(self, mocker) -> None:
        """Empty DataFrame should return empty list."""
        mock_ak = mocker.MagicMock()
        mock_ak.stock_gpzy_pledge_ratio_detail_em.return_value = pd.DataFrame()
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        result = await client.get_equity_pledge_ratio_detail()

        assert result == []

    async def test_none_dataframe_returns_empty_list(self, mocker) -> None:
        """None DataFrame should return empty list."""
        mock_ak = mocker.MagicMock()
        mock_ak.stock_gpzy_pledge_ratio_detail_em.return_value = None
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        result = await client.get_equity_pledge_ratio_detail()

        assert result == []
