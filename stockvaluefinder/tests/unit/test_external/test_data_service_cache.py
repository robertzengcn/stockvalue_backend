"""Unit tests for cache integration in ExternalDataService."""

import os
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from stockvaluefinder.external.data_service import ExternalDataService
from stockvaluefinder.utils.cache import CacheManager


def _make_mock_cache() -> tuple[MagicMock, CacheManager]:
    """Create a mock CacheManager with faked Redis connection.

    Returns:
        Tuple of (mock_redis, cache_manager) for assertion use.
    """
    mock_redis = AsyncMock()
    cache = CacheManager(redis_url="redis://localhost:6379/0")
    cache._redis = mock_redis
    cache._connected = True
    return mock_redis, cache


def _make_service_with_cache(
    cache: CacheManager | None = None,
    cache_version: str = "v1",
) -> ExternalDataService:
    """Create an ExternalDataService with optional cache.

    Args:
        cache: CacheManager instance or None
        cache_version: Cache key version string

    Returns:
        Configured ExternalDataService instance
    """
    service = ExternalDataService(
        tushare_token="",
        enable_akshare=True,
        enable_efinance=True,
        cache=cache,
        cache_version=cache_version,
    )
    service._initialized = True
    return service


@pytest.mark.asyncio
class TestFinancialReportCache:
    """Tests for caching in get_financial_report."""

    async def test_cache_hit_returns_cached_data(self) -> None:
        """Cache hit should return cached data without calling upstream."""
        import json

        cached_report = {
            "ticker": "600519.SH",
            "fiscal_year": 2023,
            "revenue": "50000000000",
            "_cache": {"hit": False, "cached_at": "2024-01-01T00:00:00Z"},
        }
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_report))

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        service._akshare = mock_akshare

        result = await service.get_financial_report("600519.SH", 2023)

        assert result["ticker"] == "600519.SH"
        assert result["fiscal_year"] == 2023
        assert result["_cache"]["hit"] is True
        # Upstream should NOT have been called
        mock_akshare.get_profit_sheet.assert_not_called()

    async def test_cache_miss_fetches_and_stores(self) -> None:
        """Cache miss should fetch from upstream and store result."""
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        service = _make_service_with_cache(cache=cache)

        mock_akshare = AsyncMock()
        mock_akshare.get_profit_sheet.return_value = [
            {
                "REPORT_DATE": "20231231",
                "TOTAL_OPERATE_INCOME": "50000000000",
                "NETPROFIT": "10000000000",
                "OPERATE_COST": "30000000000",
                "TOTAL_OPERATE_COST": "40000000000",
            }
        ]
        mock_akshare.get_balance_sheet.return_value = [
            {
                "REPORT_DATE": "20231231",
                "TOTAL_ASSETS": "100000000000",
                "TOTAL_LIABILITIES": "30000000000",
                "TOTAL_EQUITY": "70000000000",
                "ACCOUNTS_RECE": "5000000000",
                "INVENTORY": "8000000000",
                "FIXED_ASSET": "40000000000",
                "GOODWILL": "2000000000",
                "MONETARYFUNDS": "15000000000",
                "LONG_LOAN": "8000000000",
                "TOTAL_CURRENT_ASSETS": "45000000000",
            }
        ]
        mock_akshare.get_cash_flow_sheet.return_value = [
            {
                "REPORT_DATE": "20231231",
                "NETCASH_OPERATE": "12000000000",
            }
        ]
        service._akshare = mock_akshare

        result = await service.get_financial_report("600519.SH", 2023)

        assert result["ticker"] == "600519.SH"
        assert result["fiscal_year"] == 2023
        assert result["_cache"]["hit"] is False
        assert result["_cache"]["cached_at"] is not None
        # Upstream should have been called
        mock_akshare.get_profit_sheet.assert_called_once()
        # Result should have been stored in cache
        mock_redis.setex.assert_called_once()

    async def test_dev_mode_bypasses_cache(self) -> None:
        """Development mode should skip cache entirely."""
        mock_redis, cache = _make_mock_cache()

        service = _make_service_with_cache(cache=cache)

        with patch.dict(os.environ, {"DEVELOPMENT_MODE": "true"}):
            # All upstream sources disabled
            service._akshare = None
            service._efinance = None
            service._tushare = None

            result = await service.get_financial_report("600519.SH", 2023)

            assert result["ticker"] == "600519.SH"
            assert result["fiscal_year"] == 2023
            # Cache should NOT have been checked
            mock_redis.get.assert_not_called()
            mock_redis.setex.assert_not_called()

    async def test_none_cache_works_without_redis(self) -> None:
        """Service with cache=None should work normally (no caching)."""
        service = _make_service_with_cache(cache=None)

        mock_akshare = AsyncMock()
        mock_akshare.get_profit_sheet.return_value = [
            {
                "REPORT_DATE": "20231231",
                "TOTAL_OPERATE_INCOME": "50000000000",
                "NETPROFIT": "10000000000",
                "OPERATE_COST": "30000000000",
                "TOTAL_OPERATE_COST": "40000000000",
            }
        ]
        mock_akshare.get_balance_sheet.return_value = [
            {
                "REPORT_DATE": "20231231",
                "TOTAL_ASSETS": "100000000000",
                "TOTAL_LIABILITIES": "30000000000",
                "TOTAL_EQUITY": "70000000000",
                "ACCOUNTS_RECE": "5000000000",
                "INVENTORY": "8000000000",
                "FIXED_ASSET": "40000000000",
                "GOODWILL": "2000000000",
                "MONETARYFUNDS": "15000000000",
                "LONG_LOAN": "8000000000",
                "TOTAL_CURRENT_ASSETS": "45000000000",
            }
        ]
        mock_akshare.get_cash_flow_sheet.return_value = [
            {
                "REPORT_DATE": "20231231",
                "NETCASH_OPERATE": "12000000000",
            }
        ]
        service._akshare = mock_akshare

        result = await service.get_financial_report("600519.SH", 2023)

        assert result["ticker"] == "600519.SH"
        # No cache metadata when cache=None
        assert "_cache" not in result

    async def test_cache_key_uses_version(self) -> None:
        """Cache key should use the configured version prefix."""
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        service = _make_service_with_cache(cache=cache, cache_version="v2")

        mock_akshare = AsyncMock()
        mock_akshare.get_profit_sheet.return_value = [
            {
                "REPORT_DATE": "20231231",
                "TOTAL_OPERATE_INCOME": "50000000000",
                "NETPROFIT": "10000000000",
                "OPERATE_COST": "30000000000",
                "TOTAL_OPERATE_COST": "40000000000",
            }
        ]
        mock_akshare.get_balance_sheet.return_value = [
            {
                "REPORT_DATE": "20231231",
                "TOTAL_ASSETS": "100000000000",
                "TOTAL_LIABILITIES": "30000000000",
                "TOTAL_EQUITY": "70000000000",
                "ACCOUNTS_RECE": "5000000000",
                "INVENTORY": "8000000000",
                "FIXED_ASSET": "40000000000",
                "GOODWILL": "2000000000",
                "MONETARYFUNDS": "15000000000",
                "LONG_LOAN": "8000000000",
                "TOTAL_CURRENT_ASSETS": "45000000000",
            }
        ]
        mock_akshare.get_cash_flow_sheet.return_value = [
            {
                "REPORT_DATE": "20231231",
                "NETCASH_OPERATE": "12000000000",
            }
        ]
        service._akshare = mock_akshare

        await service.get_financial_report("600519.SH", 2023)

        # Verify key starts with "v2:"
        setex_call = mock_redis.setex.call_args
        assert setex_call is not None
        assert setex_call[0][0].startswith("v2:fin_report:")


@pytest.mark.asyncio
class TestRemainingMethodsCache:
    """Tests for caching in remaining data service methods."""

    async def test_get_current_price_cache_hit(self) -> None:
        """get_current_price should return cached price on cache hit."""
        import json

        # Non-dict values are wrapped in {"data": value, "_cache": {...}}
        cached_data = {
            "data": "1850.50",
            "_cache": {"hit": False, "cached_at": "2024-01-01T00:00:00Z"},
        }
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        service = _make_service_with_cache(cache=cache)
        mock_efinance = AsyncMock()
        service._efinance = mock_efinance

        result = await service.get_current_price("600519.SH")

        assert result == Decimal("1850.50")
        mock_efinance.get_latest_trade_price.assert_not_called()

    async def test_get_current_price_cache_miss_stores(self) -> None:
        """get_current_price should fetch and cache on miss."""
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        service = _make_service_with_cache(cache=cache)
        mock_efinance = AsyncMock()
        mock_efinance.get_latest_trade_price = AsyncMock(return_value=1850.50)
        service._efinance = mock_efinance

        result = await service.get_current_price("600519.SH")

        assert result == Decimal("1850.50")
        # TTL should be 300 (price cache)
        setex_call = mock_redis.setex.call_args
        assert setex_call is not None
        assert setex_call[0][1] == 300
        assert "v1:price:" in setex_call[0][0]

    async def test_get_shares_outstanding_cache_hit(self) -> None:
        """get_shares_outstanding should return cached shares on cache hit."""
        import json

        # Non-dict float value wrapped in {"data": value, "_cache": {...}}
        cached_data = {
            "data": 1256.0,
            "_cache": {"hit": False, "cached_at": "2024-01-01T00:00:00Z"},
        }
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        service._akshare = mock_akshare

        result = await service.get_shares_outstanding("600519.SH")

        assert result == 1256.0
        mock_akshare.get_shares_outstanding.assert_not_called()

    async def test_get_shares_outstanding_cache_miss_stores(self) -> None:
        """get_shares_outstanding should fetch and cache on miss."""
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        mock_akshare.get_shares_outstanding = AsyncMock(return_value=1256000000)
        service._akshare = mock_akshare

        result = await service.get_shares_outstanding("600519.SH")

        assert result == 1256.0
        # TTL should be 86400 (shares cache)
        setex_call = mock_redis.setex.call_args
        assert setex_call is not None
        assert setex_call[0][1] == 86400
        assert "v1:shares:" in setex_call[0][0]

    async def test_get_free_cash_flow_cache_hit(self) -> None:
        """get_free_cash_flow should return cached FCF on cache hit."""
        import json

        cached_data = {
            "data": 5000.0,
            "_cache": {"hit": False, "cached_at": "2024-01-01T00:00:00Z"},
        }
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        service._akshare = mock_akshare

        result = await service.get_free_cash_flow("600519.SH", "20231231")

        assert result == 5000.0
        mock_akshare.get_cash_flow_sheet.assert_not_called()

    async def test_get_free_cash_flow_cache_miss_stores(self) -> None:
        """get_free_cash_flow should fetch and cache on miss."""
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        mock_akshare.get_cash_flow_sheet.return_value = [
            {
                "REPORT_DATE": "20231231",
                "NETCASH_OPERATE": 12000000000,
                "CONSTRUCT_LONG_ASSET": 2000000000,
            }
        ]
        service._akshare = mock_akshare

        result = await service.get_free_cash_flow("600519.SH", "20231231")

        assert result == 10000.0  # (12000000000 - 2000000000) / 1_000_000
        setex_call = mock_redis.setex.call_args
        assert setex_call is not None
        assert setex_call[0][1] == 86400
        assert "v1:fcf:" in setex_call[0][0]

    async def test_get_dividend_yield_cache_hit(self) -> None:
        """get_dividend_yield should return cached yield on cache hit."""
        import json

        cached_data = {
            "data": 0.05,
            "_cache": {"hit": False, "cached_at": "2024-01-01T00:00:00Z"},
        }
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        service._akshare = mock_akshare

        result = await service.get_dividend_yield("600519.SH")

        assert result == 0.05
        mock_akshare.get_dividend_history.assert_not_called()

    async def test_get_dividend_yield_cache_miss_stores(self) -> None:
        """get_dividend_yield should fetch and cache on miss."""
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        mock_akshare.get_stock_daily.return_value = [
            {"日期": "2024-01-02", "收盘": 1000.0, "close": 1000.0}
        ]
        mock_akshare.get_dividend_history.return_value = [
            {"公告日期": "2024-06-15", "派息": 50.0},
        ]
        service._akshare = mock_akshare

        result = await service.get_dividend_yield("600519.SH")

        assert result == 0.005  # 50/10 / 1000
        setex_call = mock_redis.setex.call_args
        assert setex_call is not None
        assert setex_call[0][1] == 86400
        assert "v1:div_yield:" in setex_call[0][0]

    async def test_get_stock_basic_cache_hit(self) -> None:
        """get_stock_basic should return cached data on cache hit."""
        import json

        # list result wrapped in {"data": [...], "_cache": {...}}
        cached_list = [
            {"code": "600519", "name": "Kweichow Moutai"},
        ]
        cached_with_meta = {
            "data": cached_list,
            "_cache": {"hit": False, "cached_at": "2024-01-01T00:00:00Z"},
        }
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_with_meta))

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        service._akshare = mock_akshare

        result = await service.get_stock_basic(ts_code="600519.SH")

        assert len(result) == 1
        assert result[0]["code"] == "600519"
        mock_akshare.get_stock_info_a.assert_not_called()

    async def test_get_stock_basic_cache_miss_stores(self) -> None:
        """get_stock_basic should fetch and cache on miss."""
        mock_redis, cache = _make_mock_cache()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        service = _make_service_with_cache(cache=cache)
        mock_akshare = AsyncMock()
        mock_akshare.get_stock_info_a.return_value = [
            {"code": "600519", "name": "Kweichow Moutai"},
        ]
        service._akshare = mock_akshare

        result = await service.get_stock_basic(ts_code="600519.SH")

        assert len(result) == 1
        # TTL should be 604800 (stock basic cache, 7 days)
        setex_call = mock_redis.setex.call_args
        assert setex_call is not None
        assert setex_call[0][1] == 604800
        assert "v1:stock_basic:" in setex_call[0][0]
