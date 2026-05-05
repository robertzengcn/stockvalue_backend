"""Tests for capital allocation data service extensions.

Tests ExternalDataService.get_buyback_data() and get_multi_year_capex()
methods, including Redis caching behavior and AKShareClient.get_repurchase_data().

Covers CAPEX-01 (buyback yield data fetch) and CAPEX-03 (CapEx extraction).
"""

from unittest.mock import AsyncMock

import pytest

from stockvaluefinder.external.data_service import ExternalDataService
from stockvaluefinder.utils.errors import ExternalAPIError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_akshare() -> AsyncMock:
    """Create a mocked AKShareClient with get_repurchase_data."""
    client = AsyncMock()
    client._available = True
    return client


@pytest.fixture
def data_service(mock_akshare: AsyncMock) -> ExternalDataService:
    """Create an initialized ExternalDataService with mocked AKShare."""
    service = ExternalDataService(
        tushare_token="",
        enable_akshare=True,
        enable_efinance=False,
        cache=None,
    )
    service._akshare = mock_akshare
    service._initialized = True
    return service


# ---------------------------------------------------------------------------
# Test 1: AKShareClient.get_repurchase_data() returns list of dicts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_repurchase_data_returns_list_of_dicts(
    mock_akshare: AsyncMock,
) -> None:
    """AKShareClient.get_repurchase_data() returns list of dicts from stock_repurchase_em()."""
    expected = [
        {"股票代码": "600519", "股票简称": "贵州茅台", "已回购金额": 100000000},
        {"股票代码": "000001", "股票简称": "平安银行", "已回购金额": 50000000},
    ]
    mock_akshare.get_repurchase_data.return_value = expected

    result = await mock_akshare.get_repurchase_data()

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["股票代码"] == "600519"
    assert result[0]["已回购金额"] == 100000000


# ---------------------------------------------------------------------------
# Test 2: get_buyback_data filters full dataset by stock code
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_buyback_data_filters_by_ticker(
    data_service: ExternalDataService,
    mock_akshare: AsyncMock,
) -> None:
    """get_buyback_data filters full dataset by stock code and returns matching records."""
    mock_akshare.get_repurchase_data.return_value = [
        {
            "股票代码": "600519",
            "股票简称": "贵州茅台",
            "已回购金额": 100000000,
            "已回购股份数量": 500000,
            "实施进度": "完成实施",
            "最新公告日期": "2024-06-01",
        },
        {
            "股票代码": "000001",
            "股票简称": "平安银行",
            "已回购金额": 50000000,
            "已回购股份数量": 300000,
            "实施进度": "完成实施",
            "最新公告日期": "2024-03-01",
        },
    ]

    result = await data_service.get_buyback_data("600519.SH")

    assert result["repurchase_amount"] == 100000000.0
    assert result["repurchase_shares"] == 500000.0
    assert result["program_status"] == "完成实施"
    assert result["data_quality"] == "COMPLETE"


# ---------------------------------------------------------------------------
# Test 3: get_buyback_data caches full dataset with key buyback_full_dataset
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_buyback_data_caches_full_dataset(
    data_service: ExternalDataService,
    mock_akshare: AsyncMock,
) -> None:
    """get_buyback_data caches full dataset with key buyback_full_dataset and TTL 86400."""
    mock_akshare.get_repurchase_data.return_value = [
        {
            "股票代码": "600519",
            "已回购金额": 100000000,
            "已回购股份数量": 500000,
            "实施进度": "完成实施",
            "最新公告日期": "2024-06-01",
        },
    ]

    # Create a mock cache that tracks calls
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None  # Cache miss

    data_service._cache = mock_cache

    result = await data_service.get_buyback_data("600519.SH")

    # Verify cache.set was called with key containing "buyback_full_dataset"
    assert mock_cache.set.called
    call_args = mock_cache.set.call_args
    cache_key = call_args[0][0]
    assert "buyback_full_dataset" in cache_key
    # TTL is passed as keyword argument
    assert call_args[1].get("ttl") == 86400

    assert result["repurchase_amount"] == 100000000.0


# ---------------------------------------------------------------------------
# Test 4: get_buyback_data selects most recent completed program
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_buyback_data_selects_most_recent_completed(
    data_service: ExternalDataService,
    mock_akshare: AsyncMock,
) -> None:
    """get_buyback_data selects most recent completed program (完成实施)."""
    mock_akshare.get_repurchase_data.return_value = [
        {
            "股票代码": "600519",
            "已回购金额": 50000000,
            "已回购股份数量": 250000,
            "实施进度": "实施中",
            "最新公告日期": "2024-09-01",
        },
        {
            "股票代码": "600519",
            "已回购金额": 100000000,
            "已回购股份数量": 500000,
            "实施进度": "完成实施",
            "最新公告日期": "2024-06-01",
        },
        {
            "股票代码": "600519",
            "已回购金额": 80000000,
            "已回购股份数量": 400000,
            "实施进度": "完成实施",
            "最新公告日期": "2023-12-01",
        },
    ]

    result = await data_service.get_buyback_data("600519.SH")

    # Should select the most recent COMPLETED program (2024-06-01)
    assert result["repurchase_amount"] == 100000000.0
    assert result["program_status"] == "完成实施"
    assert result["data_quality"] == "COMPLETE"


# ---------------------------------------------------------------------------
# Test 5: get_buyback_data falls back to in-progress with INCOMPLETE flag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_buyback_data_falls_back_to_in_progress(
    data_service: ExternalDataService,
    mock_akshare: AsyncMock,
) -> None:
    """get_buyback_data falls back to '实施中' with data_quality='INCOMPLETE' when no completed program."""
    mock_akshare.get_repurchase_data.return_value = [
        {
            "股票代码": "600519",
            "已回购金额": 50000000,
            "已回购股份数量": 250000,
            "实施进度": "实施中",
            "最新公告日期": "2024-09-01",
        },
    ]

    result = await data_service.get_buyback_data("600519.SH")

    assert result["repurchase_amount"] == 50000000.0
    assert result["program_status"] == "实施中"
    assert result["data_quality"] == "INCOMPLETE"


# ---------------------------------------------------------------------------
# Test 6: get_multi_year_capex returns list of dicts with capex field
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_multi_year_capex_returns_capex_data(
    data_service: ExternalDataService,
    mock_akshare: AsyncMock,
) -> None:
    """get_multi_year_capex returns list of dicts with capex field from CONSTRUCT_LONG_ASSET."""
    mock_akshare.get_cash_flow_sheet.return_value = [
        {
            "REPORT_DATE": "2023-12-31",
            "CONSTRUCT_LONG_ASSET": -3000000000,
        },
        {
            "REPORT_DATE": "2022-12-31",
            "CONSTRUCT_LONG_ASSET": -2500000000,
        },
    ]

    result = await data_service.get_multi_year_capex("600519.SH", 2)

    assert isinstance(result, list)
    assert len(result) == 2
    # Sorted by fiscal_year descending
    assert result[0]["fiscal_year"] == 2023
    assert result[0]["capex"] == -3000000000.0
    assert result[1]["fiscal_year"] == 2022
    assert result[1]["capex"] == -2500000000.0


# ---------------------------------------------------------------------------
# Test 7: get_multi_year_capex handles NaN CapEx values
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_multi_year_capex_handles_nan(
    data_service: ExternalDataService,
    mock_akshare: AsyncMock,
) -> None:
    """get_multi_year_capex normalizes NaN CapEx values to 0.0."""
    mock_akshare.get_cash_flow_sheet.return_value = [
        {
            "REPORT_DATE": "2023-12-31",
            "CONSTRUCT_LONG_ASSET": float("nan"),
        },
        {
            "REPORT_DATE": "2022-12-31",
            "CONSTRUCT_LONG_ASSET": -2000000000,
        },
    ]

    result = await data_service.get_multi_year_capex("600519.SH", 2)

    assert result[0]["capex"] == 0.0  # NaN normalized to 0.0
    assert result[1]["capex"] == -2000000000.0


# ---------------------------------------------------------------------------
# Test 8: get_buyback_data returns empty result when ticker not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_buyback_data_returns_no_data_when_ticker_not_found(
    data_service: ExternalDataService,
    mock_akshare: AsyncMock,
) -> None:
    """get_buyback_data returns empty result with buyback_yield=None when ticker not found."""
    mock_akshare.get_repurchase_data.return_value = [
        {
            "股票代码": "000001",
            "已回购金额": 50000000,
            "实施进度": "完成实施",
            "最新公告日期": "2024-03-01",
        },
    ]

    result = await data_service.get_buyback_data("600519.SH")

    assert result["repurchase_amount"] is None
    assert result["data_quality"] == "NO_DATA"


# ---------------------------------------------------------------------------
# Test: get_buyback_data raises when not initialized
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_buyback_data_raises_when_not_initialized() -> None:
    """get_buyback_data raises ExternalAPIError when service not initialized."""
    service = ExternalDataService(
        tushare_token="",
        enable_akshare=True,
    )
    service._initialized = False

    with pytest.raises(ExternalAPIError, match="not initialized"):
        await service.get_buyback_data("600519.SH")


# ---------------------------------------------------------------------------
# Test: get_multi_year_capex raises when not initialized
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_multi_year_capex_raises_when_not_initialized() -> None:
    """get_multi_year_capex raises ExternalAPIError when service not initialized."""
    service = ExternalDataService(
        tushare_token="",
        enable_akshare=True,
    )
    service._initialized = False

    with pytest.raises(ExternalAPIError, match="not initialized"):
        await service.get_multi_year_capex("600519.SH")


# ---------------------------------------------------------------------------
# Test: get_multi_year_capex with Chinese field name fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_multi_year_capex_chinese_field_fallback(
    data_service: ExternalDataService,
    mock_akshare: AsyncMock,
) -> None:
    """get_multi_year_capex falls back to Chinese field name for CapEx."""
    mock_akshare.get_cash_flow_sheet.return_value = [
        {
            "REPORT_DATE": "2023-12-31",
            "购建固定资产、无形资产和其他长期资产支付的现金": -3500000000,
        },
    ]

    result = await data_service.get_multi_year_capex("600519.SH", 1)

    assert result[0]["capex"] == -3500000000.0


# ---------------------------------------------------------------------------
# Test: get_buyback_data handles NaN repurchase amount
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_buyback_data_handles_nan_amount(
    data_service: ExternalDataService,
    mock_akshare: AsyncMock,
) -> None:
    """get_buyback_data handles NaN in 已回购金额 by normalizing to None."""
    mock_akshare.get_repurchase_data.return_value = [
        {
            "股票代码": "600519",
            "已回购金额": float("nan"),
            "已回购股份数量": 500000,
            "实施进度": "完成实施",
            "最新公告日期": "2024-06-01",
        },
    ]

    result = await data_service.get_buyback_data("600519.SH")

    assert result["repurchase_amount"] is None


# ---------------------------------------------------------------------------
# Test: get_multi_year_capex with empty result
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_multi_year_capex_empty_result(
    data_service: ExternalDataService,
    mock_akshare: AsyncMock,
) -> None:
    """get_multi_year_capex returns empty list when no data available."""
    mock_akshare.get_cash_flow_sheet.return_value = []

    result = await data_service.get_multi_year_capex("600519.SH", 2)

    assert result == []
