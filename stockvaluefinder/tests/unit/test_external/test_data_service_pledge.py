"""Unit tests for ExternalDataService equity pledge methods."""

import json
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from stockvaluefinder.external.data_service import (
    PLEDGE_DETAIL_FIELD_MAP,
    PLEDGE_RATIO_FIELD_MAP,
    ExternalDataService,
)
from stockvaluefinder.models.equity_pledge import (
    DataFreshness,
    EquityPledgeDetail,
    EquityPledgeSnapshot,
)
from stockvaluefinder.utils.cache import CacheManager
from stockvaluefinder.utils.errors import ExternalAPIError


def _make_mock_cache() -> tuple[MagicMock, CacheManager]:
    """Create a mock CacheManager with faked Redis connection."""
    mock_redis = AsyncMock()
    cache = CacheManager(redis_url="redis://localhost:6379/0")
    cache._redis = mock_redis
    cache._connected = True
    return mock_redis, cache


def _make_service_with_cache(
    cache: CacheManager | None = None,
    cache_version: str = "v1",
) -> ExternalDataService:
    """Create an ExternalDataService with optional cache."""
    service = ExternalDataService(
        tushare_token="",
        enable_akshare=True,
        enable_efinance=True,
        cache=cache,
        cache_version=cache_version,
    )
    service._initialized = True
    return service


def _make_ratio_bulk_data() -> list[dict[str, object]]:
    """Create sample bulk ratio data mimicking AKShare response."""
    return [
        {
            "股票代码": "600519",
            "股票简称": "贵州茅台",
            "交易日期": "2024-06-05",
            "所属行业": "白酒",
            "质押比例": 35.5,
            "质押股数": 100000.0,
            "质押市值": 50000000.0,
            "质押笔数": 10,
            "无限售股质押数": 80000.0,
            "限售股质押数": 20000.0,
            "近一年涨跌幅": -5.2,
        },
        {
            "股票代码": "000002",
            "股票简称": "万科A",
            "交易日期": "2024-06-05",
            "所属行业": "房地产",
            "质押比例": 12.3,
            "质押股数": 50000.0,
            "质押市值": 10000000.0,
            "质押笔数": 5,
            "无限售股质押数": 40000.0,
            "限售股质押数": 10000.0,
            "近一年涨跌幅": -15.0,
        },
    ]


def _make_detail_bulk_data() -> list[dict[str, object]]:
    """Create sample bulk detail data mimicking AKShare response."""
    return [
        {
            "股票代码": "600519",
            "股票简称": "贵州茅台",
            "股东名称": "XX投资公司",
            "质押股份数量": 1000000.0,
            "占所持股份比例": 50.0,
            "占总股本比例": 5.0,
            "质押机构": "XX证券",
            "最新价": 1800.0,
            "质押日收盘价": 1750.0,
            "预估平仓线": 1200.0,
            "质押开始日期": "2024-01-15",
            "公告日期": "2024-01-16",
        },
    ]


@pytest.mark.asyncio
class TestEquityPledgeSnapshot:
    """Tests for get_equity_pledge_snapshot method."""

    async def test_cache_hit_returns_filtered_data_for_matching_ticker(
        self,
    ) -> None:
        """Cache hit returns filtered data for matching ticker."""
        bulk_data = _make_ratio_bulk_data()
        cached_data = {
            "data": bulk_data,
            "_cache": {"hit": False, "cached_at": "2024-06-05T00:00:00Z"},
        }
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        service._akshare = mock_akshare

        result = await service.get_equity_pledge_snapshot(
            "600519.SH", trade_date="20240605"
        )

        assert isinstance(result, EquityPledgeSnapshot)
        assert result.ticker == "600519.SH"
        assert result.company_pledge_ratio == 35.5
        # Upstream should NOT have been called (cache hit)
        mock_akshare.get_equity_pledge_ratio_by_date.assert_not_called()

    async def test_zero_pledge_snapshot_when_ticker_absent_from_nonempty_bulk(
        self,
    ) -> None:
        """Missing ticker from non-empty bulk returns zero-pledge snapshot (D-08)."""
        bulk_data = _make_ratio_bulk_data()
        cached_data = {
            "data": bulk_data,
            "_cache": {"hit": False, "cached_at": "2024-06-05T00:00:00Z"},
        }
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        service._akshare = mock_akshare

        result = await service.get_equity_pledge_snapshot(
            "601988.SH", trade_date="20240605"
        )

        assert isinstance(result, EquityPledgeSnapshot)
        assert result.ticker == "601988.SH"
        assert result.company_pledge_ratio == 0.0
        assert result.data_quality.freshness == DataFreshness.CURRENT

    async def test_unavailable_freshness_when_bulk_empty(self) -> None:
        """Empty bulk response returns UNAVAILABLE freshness (D-09)."""
        cached_data = {
            "data": [],
            "_cache": {"hit": False, "cached_at": "2024-06-05T00:00:00Z"},
        }
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        service._akshare = mock_akshare

        result = await service.get_equity_pledge_snapshot(
            "600519.SH", trade_date="20240605"
        )

        assert isinstance(result, EquityPledgeSnapshot)
        assert result.ticker == "600519.SH"
        assert result.data_quality.freshness == DataFreshness.UNAVAILABLE
        assert result.company_pledge_ratio is None

    async def test_cache_key_includes_trade_date_not_ticker(self) -> None:
        """Cache key should include trade date, not ticker."""
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        mock_akshare.get_equity_pledge_ratio_by_date.return_value = (
            _make_ratio_bulk_data()
        )
        service._akshare = mock_akshare

        await service.get_equity_pledge_snapshot("600519.SH", trade_date="20240605")

        setex_call = mock_redis.setex.call_args
        assert setex_call is not None
        cache_key = setex_call[0][0]
        assert "20240605" in cache_key
        assert "600519" not in cache_key

    async def test_field_mapping_converts_chinese_to_english(self) -> None:
        """Field mapping converts all Chinese column names to English."""
        bulk_data = _make_ratio_bulk_data()
        cached_data = {
            "data": bulk_data,
            "_cache": {"hit": False, "cached_at": "2024-06-05T00:00:00Z"},
        }
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        service._akshare = mock_akshare

        result = await service.get_equity_pledge_snapshot(
            "600519.SH", trade_date="20240605"
        )

        assert result.ticker == "600519.SH"
        assert result.company_pledge_ratio == 35.5
        assert result.pledged_shares == Decimal("100000")
        assert result.pledge_market_value == Decimal("50000000")
        assert result.pledge_count == 10
        assert result.unrestricted_pledged_shares == Decimal("80000")
        assert result.restricted_pledged_shares == Decimal("20000")
        assert result.one_year_price_change == -5.2
        assert result.industry == "白酒"

    async def test_nan_values_normalized_to_none(self) -> None:
        """NaN values in AKShare data should be normalized to None."""
        bulk_data = [
            {
                "股票代码": "600519",
                "股票简称": "贵州茅台",
                "交易日期": "2024-06-05",
                "所属行业": "白酒",
                "质押比例": float("nan"),
                "质押股数": 100000.0,
                "质押市值": float("nan"),
                "质押笔数": 10,
                "无限售股质押数": float("nan"),
                "限售股质押数": float("nan"),
                "近一年涨跌幅": float("nan"),
            }
        ]
        cached_data = {
            "data": bulk_data,
            "_cache": {"hit": False, "cached_at": "2024-06-05T00:00:00Z"},
        }
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        service._akshare = mock_akshare

        result = await service.get_equity_pledge_snapshot(
            "600519.SH", trade_date="20240605"
        )

        assert isinstance(result, EquityPledgeSnapshot)
        assert result.company_pledge_ratio is None
        assert result.pledge_market_value is None
        assert result.one_year_price_change is None
        # Non-NaN fields should be populated
        assert result.pledged_shares == Decimal("100000")
        assert result.pledge_count == 10

    async def test_auto_date_discovery_when_no_trade_date(self, mocker) -> None:
        """When no trade_date specified, system auto-discovers latest date."""
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        mock_akshare.get_equity_pledge_ratio_by_date.return_value = (
            _make_ratio_bulk_data()
        )
        service._akshare = mock_akshare

        with patch("stockvaluefinder.external.data_service.date") as mock_date:
            mock_date.today.return_value = date(2024, 6, 5)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

            result = await service.get_equity_pledge_snapshot("600519.SH")

        assert isinstance(result, EquityPledgeSnapshot)
        assert result.ticker == "600519.SH"


@pytest.mark.asyncio
class TestEquityPledgeDetails:
    """Tests for get_equity_pledge_details method."""

    async def test_returns_list_of_equity_pledge_detail_for_matching_ticker(
        self,
    ) -> None:
        """Returns list of EquityPledgeDetail for matching ticker."""
        bulk_data = _make_detail_bulk_data()
        cached_data = {
            "data": bulk_data,
            "_cache": {"hit": False, "cached_at": "2024-06-05T00:00:00Z"},
        }
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        service._akshare = mock_akshare

        result = await service.get_equity_pledge_details("600519.SH")

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], EquityPledgeDetail)
        assert result[0].ticker == "600519.SH"
        assert result[0].holder_name == "XX投资公司"
        assert result[0].pledge_amount == Decimal("1000000")
        assert result[0].source == "akshare"

    async def test_empty_list_when_no_matching_records(self) -> None:
        """Returns empty list when no matching records in bulk."""
        bulk_data = _make_detail_bulk_data()
        cached_data = {
            "data": bulk_data,
            "_cache": {"hit": False, "cached_at": "2024-06-05T00:00:00Z"},
        }
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        service._akshare = mock_akshare

        result = await service.get_equity_pledge_details("601988.SH")

        assert result == []

    async def test_cache_key_is_equity_pledge_ratio_detail_latest(self) -> None:
        """Cache key should be equity_pledge:ratio_detail:latest."""
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        mock_akshare.get_equity_pledge_ratio_detail.return_value = (
            _make_detail_bulk_data()
        )
        service._akshare = mock_akshare

        await service.get_equity_pledge_details("600519.SH")

        setex_call = mock_redis.setex.call_args
        assert setex_call is not None
        cache_key = setex_call[0][0]
        assert "equity_pledge" in cache_key
        assert "ratio_detail" in cache_key
        assert "latest" in cache_key


@pytest.mark.asyncio
class TestDateDiscovery:
    """Tests for _find_latest_pledge_date method."""

    async def test_returns_first_date_with_nonempty_data(self, mocker) -> None:
        """Returns first date that returns non-empty data."""
        service = _make_service_with_cache(cache=None)
        mock_akshare = AsyncMock()
        # First call (today) returns empty, second call (yesterday) returns data
        mock_akshare.get_equity_pledge_ratio_by_date.side_effect = [
            [],
            [{"股票代码": "600519"}],
        ]
        service._akshare = mock_akshare

        with patch("stockvaluefinder.external.data_service.date") as mock_date:
            mock_date.today.return_value = date(2024, 6, 5)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

            result = await service._find_latest_pledge_date()

        assert result == "20240604"
        assert mock_akshare.get_equity_pledge_ratio_by_date.call_count == 2

    async def test_returns_none_when_all_10_dates_fail(self, mocker) -> None:
        """Returns None when all 10 dates return empty data."""
        service = _make_service_with_cache(cache=None)
        mock_akshare = AsyncMock()
        mock_akshare.get_equity_pledge_ratio_by_date.return_value = []
        service._akshare = mock_akshare

        with patch("stockvaluefinder.external.data_service.date") as mock_date:
            mock_date.today.return_value = date(2024, 6, 5)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

            result = await service._find_latest_pledge_date()

        assert result is None
        assert mock_akshare.get_equity_pledge_ratio_by_date.call_count == 10

    async def test_skips_external_api_error_and_continues(self, mocker) -> None:
        """Skips ExternalAPIError and continues to next date."""
        service = _make_service_with_cache(cache=None)
        mock_akshare = AsyncMock()
        mock_akshare.get_equity_pledge_ratio_by_date.side_effect = [
            ExternalAPIError("Connection reset"),
            [{"股票代码": "600519"}],
        ]
        service._akshare = mock_akshare

        with patch("stockvaluefinder.external.data_service.date") as mock_date:
            mock_date.today.return_value = date(2024, 6, 5)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

            result = await service._find_latest_pledge_date()

        assert result == "20240604"

    async def test_tries_dates_in_reverse_chronological_order(self, mocker) -> None:
        """Tries dates in reverse chronological order (today first)."""
        service = _make_service_with_cache(cache=None)
        mock_akshare = AsyncMock()
        call_dates: list[str] = []

        async def _track_call(trade_date: str) -> list[dict[str, str]]:
            call_dates.append(trade_date)
            return []

        mock_akshare.get_equity_pledge_ratio_by_date.side_effect = _track_call
        service._akshare = mock_akshare

        with patch("stockvaluefinder.external.data_service.date") as mock_date:
            mock_date.today.return_value = date(2024, 6, 5)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

            await service._find_latest_pledge_date()

        assert call_dates[0] == "20240605"
        assert call_dates[1] == "20240604"
        assert call_dates[2] == "20240603"


@pytest.mark.asyncio
class TestFieldMapConstants:
    """Tests for PLEDGE_RATIO_FIELD_MAP and PLEDGE_DETAIL_FIELD_MAP."""

    def test_pledge_ratio_field_map_has_expected_keys(self) -> None:
        """PLEDGE_RATIO_FIELD_MAP should have all expected Chinese keys."""
        expected = {
            "股票代码",
            "股票简称",
            "交易日期",
            "所属行业",
            "质押比例",
            "质押股数",
            "质押市值",
            "质押笔数",
            "无限售股质押数",
            "限售股质押数",
            "近一年涨跌幅",
        }
        assert set(PLEDGE_RATIO_FIELD_MAP.keys()) == expected

    def test_pledge_detail_field_map_has_expected_keys(self) -> None:
        """PLEDGE_DETAIL_FIELD_MAP should have all expected Chinese keys."""
        expected = {
            "股票代码",
            "股票简称",
            "股东名称",
            "质押股份数量",
            "占所持股份比例",
            "占总股本比例",
            "质押机构",
            "最新价",
            "质押日收盘价",
            "预估平仓线",
            "质押开始日期",
            "公告日期",
        }
        assert set(PLEDGE_DETAIL_FIELD_MAP.keys()) == expected


@pytest.mark.asyncio
class TestTushareFallback:
    """Tests for Tushare fallback path (skeleton test)."""

    async def test_tushare_fallback_skeleton(self) -> None:
        """When AKShare detail returns empty, returns empty list (Tushare not configured)."""
        cached_data = {
            "data": [],
            "_cache": {"hit": False, "cached_at": "2024-06-05T00:00:00Z"},
        }
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        service._akshare = mock_akshare

        result = await service.get_equity_pledge_details("600519.SH")

        # With empty bulk, returns empty list (no Tushare fallback yet)
        assert result == []
