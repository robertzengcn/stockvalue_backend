"""Unit tests for AKShare business description fetching.

Tests the get_stock_business_description() method on AKShareClient,
verifying it uses stock_profile_cninfo (NOT stock_individual_info_em)
and correctly extracts main_business and business_scope fields.
"""

import pandas as pd  # type: ignore[import-untyped]
import pytest

from stockvaluefinder.external.akshare_client import AKShareClient


@pytest.mark.asyncio
class TestGetStockBusinessDescription:
    """Test suite for AKShareClient.get_stock_business_description."""

    async def test_extracts_main_business_and_scope(self, mocker):
        """Test successful extraction of both fields from stock_profile_cninfo."""
        mock_ak = mocker.MagicMock()
        mock_df = pd.DataFrame(
            [
                {
                    "主营业务": "贵州茅台酒系列产品的产品研制、酿造生产、包装和销售。",
                    "经营范围": "茅台酒系列产品的生产与销售；饮料、食品、包装材料的生产、销售",
                    "A股代码": "600519",
                    "A股简称": "贵州茅台",
                }
            ]
        )
        mock_ak.stock_profile_cninfo.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        result = await client.get_stock_business_description("600519")

        assert (
            result["main_business"]
            == "贵州茅台酒系列产品的产品研制、酿造生产、包装和销售。"
        )
        assert "茅台酒" in result["business_scope"]

    async def test_returns_empty_dict_on_none_dataframe(self, mocker):
        """Test that None DataFrame returns empty strings."""
        mock_ak = mocker.MagicMock()
        mock_ak.stock_profile_cninfo.return_value = None
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        result = await client.get_stock_business_description("600519")

        assert result == {"main_business": "", "business_scope": ""}

    async def test_returns_empty_dict_on_empty_dataframe(self, mocker):
        """Test that empty DataFrame returns empty strings."""
        mock_ak = mocker.MagicMock()
        mock_ak.stock_profile_cninfo.return_value = pd.DataFrame()
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        result = await client.get_stock_business_description("600519")

        assert result == {"main_business": "", "business_scope": ""}

    async def test_handles_missing_columns_gracefully(self, mocker):
        """Test that missing expected columns returns empty strings."""
        mock_ak = mocker.MagicMock()
        mock_df = pd.DataFrame([{"A股代码": "600519", "A股简称": "贵州茅台"}])
        mock_ak.stock_profile_cninfo.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        result = await client.get_stock_business_description("600519")

        # Missing columns should default to empty string
        assert result["main_business"] == ""
        assert result["business_scope"] == ""

    async def test_calls_stock_profile_cninfo_not_individual_info(self, mocker):
        """Test that stock_profile_cninfo is used, NOT stock_individual_info_em."""
        mock_ak = mocker.MagicMock()
        mock_df = pd.DataFrame([{"主营业务": "测试业务", "经营范围": "测试范围"}])
        mock_ak.stock_profile_cninfo.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        await client.get_stock_business_description("600519")

        # Verify stock_profile_cninfo was called with correct symbol
        mock_ak.stock_profile_cninfo.assert_called_once_with(symbol="600519")
        # Verify stock_individual_info_em was NOT called
        mock_ak.stock_individual_info_em.assert_not_called()

    async def test_passes_six_digit_symbol_directly(self, mocker):
        """Test that the 6-digit code is passed directly to stock_profile_cninfo."""
        mock_ak = mocker.MagicMock()
        mock_df = pd.DataFrame([{"主营业务": "房地产", "经营范围": "房地产开发"}])
        mock_ak.stock_profile_cninfo.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        await client.get_stock_business_description("000002")

        mock_ak.stock_profile_cninfo.assert_called_once_with(symbol="000002")

    async def test_returns_dict_with_required_keys(self, mocker):
        """Test that result always has main_business and business_scope keys."""
        mock_ak = mocker.MagicMock()
        mock_df = pd.DataFrame(
            [{"主营业务": "半导体设计", "经营范围": "集成电路设计研发"}]
        )
        mock_ak.stock_profile_cninfo.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        result = await client.get_stock_business_description("603986")

        assert "main_business" in result
        assert "business_scope" in result
        assert len(result) == 2


class TestStockBusinessDescDoesNotUseIndividualInfoEm:
    """Verify the method does NOT use stock_individual_info_em at source level."""

    def test_get_stock_business_description_source_code(self):
        """Static check: source code must contain stock_profile_cninfo."""
        import inspect

        source = inspect.getsource(AKShareClient.get_stock_business_description)
        assert "stock_profile_cninfo" in source, (
            "get_stock_business_description must use stock_profile_cninfo"
        )
        assert "stock_individual_info_em" not in source, (
            "get_stock_business_description must NOT use stock_individual_info_em"
        )
