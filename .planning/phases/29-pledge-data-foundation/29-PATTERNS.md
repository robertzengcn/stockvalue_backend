# Phase 29: Pledge Data Foundation - Pattern Map

**Mapped:** 2026-06-06
**Files analyzed:** 8
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `stockvaluefinder/models/equity_pledge.py` (NEW) | model | request-response | `stockvaluefinder/models/risk.py` | exact |
| `stockvaluefinder/utils/validators.py` (MODIFY) | utility | transform | `stockvaluefinder/utils/validators.py` (itself) | exact |
| `stockvaluefinder/external/akshare_client.py` (MODIFY) | client | request-response | `stockvaluefinder/external/akshare_client.py` `get_repurchase_data()` | exact |
| `stockvaluefinder/external/data_service.py` (MODIFY) | service | request-response | `stockvaluefinder/external/data_service.py` `get_buyback_data()` | exact |
| `tests/unit/test_utils/test_validators.py` (MODIFY) | test | request-response | `tests/unit/test_utils/test_validators.py` `TestValidateTickerFormat` | exact |
| `tests/unit/test_models/test_equity_pledge.py` (NEW) | test | request-response | `tests/unit/test_utils/test_validators.py` `TestValidateTickerFormat` (Pydantic model test pattern) | role-match |
| `tests/unit/test_external/test_akshare_equity_pledge.py` (NEW) | test | request-response | `tests/unit/test_external/test_akshare_client.py` | exact |
| `tests/unit/test_external/test_data_service_pledge.py` (NEW) | test | request-response | `tests/unit/test_external/test_data_service_cache.py` | exact |

## Pattern Assignments

### `stockvaluefinder/models/equity_pledge.py` (NEW -- model, request-response)

**Analog:** `stockvaluefinder/models/risk.py`

This file defines Pydantic domain models for equity pledge data. Follow the same pattern as `risk.py`: frozen models, `Field(...)` with descriptions, optional fields with `| None = None`, nested sub-models.

**Imports pattern** (from `risk.py` lines 1-9):
```python
"""Equity pledge domain models (Pydantic)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from stockvaluefinder.models.enums import RiskLevel
```

**Enum pattern** (per tech design section 8 and existing `enums.py` pattern with `StrEnum`):
```python
from enum import Enum

class DataFreshness(str, Enum):
    """Data freshness classification for pledge data sources."""
    CURRENT = "CURRENT"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
```

**Frozen model with Field descriptions** (from `risk.py` lines 30-46, the `MScoreData` pattern):
```python
class EquityPledgeDataQuality(BaseModel):
    """Quality metadata for equity pledge data fetch."""

    model_config = {"frozen": True}

    source: str | None = Field(None, description="Data source name (e.g., 'akshare')")
    latest_date: date | None = Field(None, description="Latest available trade date")
    fetched_at: datetime | None = Field(None, description="Timestamp when data was fetched")
    freshness: DataFreshness = Field(..., description="Data freshness classification")
    warnings: list[str] = Field(default_factory=list, description="Data quality warnings")
```

**Snapshot model** (per tech design section 8, lines 411-423):
```python
class EquityPledgeSnapshot(BaseModel):
    """Company-level equity pledge summary for a single stock."""

    model_config = {"frozen": True}

    ticker: str = Field(..., description="Stock code (e.g., '600519.SH')")
    latest_date: date | None = Field(None, description="Trade date of the pledge data")
    company_pledge_ratio: float | None = Field(None, description="Company pledge ratio as percentage (e.g., 35.5 means 35.5%)")
    pledged_shares: Decimal | None = Field(None, description="Total pledged shares")
    pledge_market_value: Decimal | None = Field(None, description="Market value of pledged shares")
    pledge_count: int | None = Field(None, description="Number of pledge transactions")
    unrestricted_pledged_shares: Decimal | None = Field(None, description="Unrestricted shares pledged")
    restricted_pledged_shares: Decimal | None = Field(None, description="Restricted shares pledged")
    one_year_price_change: float | None = Field(None, description="One-year price change as percentage")
    industry: str | None = Field(None, description="Industry classification")
    data_quality: EquityPledgeDataQuality = Field(..., description="Data quality metadata")
```

**Detail model** (per tech design section 8, lines 425-442):
```python
class EquityPledgeDetail(BaseModel):
    """Important shareholder pledge detail record."""

    model_config = {"frozen": True}

    ticker: str = Field(..., description="Stock code (e.g., '600519.SH')")
    stock_name: str | None = Field(None, description="Stock name")
    holder_name: str = Field(..., description="Shareholder name")
    is_controlling_holder: bool = Field(False, description="Whether this is the controlling shareholder")
    pledge_amount: Decimal | None = Field(None, description="Number of shares pledged in this record")
    pledged_to_holding_ratio: float | None = Field(None, description="Pledged / holding ratio as percentage")
    pledged_to_total_share_ratio: float | None = Field(None, description="Pledged / total shares ratio as percentage")
    pledgee: str | None = Field(None, description="Pledgee institution")
    latest_price: float | None = Field(None, description="Latest stock price")
    pledge_date_close_price: float | None = Field(None, description="Stock closing price on pledge date")
    estimated_closeout_price: float | None = Field(None, description="Estimated forced-sell price")
    start_date: date | None = Field(None, description="Pledge start date")
    announcement_date: date | None = Field(None, description="Announcement date")
    source: str = Field(..., description="Data source identifier")
```

---

### `stockvaluefinder/utils/validators.py` (MODIFY -- add `normalize_a_share_ticker`)

**Analog:** `stockvaluefinder/utils/validators.py` itself (add new function alongside existing validators)

The existing file has pure validation functions with Google-style docstrings, type hints, and no exceptions for the normalize function (returns `str | None` per D-04).

**Existing import pattern** (lines 1-8):
```python
"""Custom Pydantic validators for StockValueFinder domain."""

import re
from decimal import Decimal, InvalidOperation

from stockvaluefinder.models.enums import Market
```

**Add logging import** (new, for warning on unsupported codes):
```python
import logging

logger = logging.getLogger(__name__)
```

**Function pattern to add** (follows `validate_ticker_format` style but returns `str | None` instead of raising):
```python
def normalize_a_share_ticker(code: str) -> str | None:
    """Normalize 6-digit A-share stock code to internal ticker format.

    Prefix mapping: 6xx -> .SH, 0xx/3xx -> .SZ.
    BSE codes (8xx/4xx) and invalid codes return None.

    Args:
        code: 6-digit stock code (e.g., '600519', '000002')

    Returns:
        Internal ticker (e.g., '600519.SH', '000002.SZ') or None
        for unsupported/invalid codes.

    Examples:
        >>> normalize_a_share_ticker("600519")
        '600519.SH'
        >>> normalize_a_share_ticker("000002")
        '000002.SZ'
        >>> normalize_a_share_ticker("300001")
        '300001.SZ'
        >>> normalize_a_share_ticker("830001") is None
        True
        >>> normalize_a_share_ticker("999999") is None
        True
    """
    code = str(code).strip()
    if len(code) != 6 or not code.isdigit():
        return None
    if code.startswith("6"):
        return f"{code}.SH"
    if code.startswith(("0", "3")):
        return f"{code}.SZ"
    logger.warning(f"Unsupported A-share stock code prefix: {code}")
    return None
```

---

### `stockvaluefinder/external/akshare_client.py` (MODIFY -- add pledge methods)

**Analog:** `stockvaluefinder/external/akshare_client.py` `get_repurchase_data()` (lines 631-650)

The new pledge methods follow the exact same `_fetch` inner function + `_run_sync` pattern as `get_repurchase_data()`. Both pledge APIs return bulk market-wide data.

**Existing method pattern to copy** (lines 631-650):
```python
async def get_repurchase_data(self) -> list[dict[str, Any]]:
    """Fetch full A-share buyback dataset from East Money.

    Returns ALL ~5088 stocks with buyback programs. Caller filters by
    stock code.  Data cached at data_service level with 24h TTL per D-01.
    """
    def _fetch() -> list[dict[str, Any]]:
        import akshare as ak

        df = ak.stock_repurchase_em()
        if df is None or df.empty:
            return []
        return df.to_dict("records")

    return await self._run_sync(_fetch)
```

**New method 1 -- `get_equity_pledge_ratio_by_date`** (follows same pattern):
```python
async def get_equity_pledge_ratio_by_date(self, trade_date: str) -> list[dict[str, Any]]:
    """Fetch A-share equity pledge ratio data for a specific trade date.

    Wraps AKShare ``stock_gpzy_pledge_ratio_em(date)``. Returns ALL stocks
    with pledge data for the given date. Caller filters by stock code.

    Args:
        trade_date: Date string in YYYYMMDD format (e.g., '20240605')

    Returns:
        List of dicts with Chinese field names.
    """
    def _fetch() -> list[dict[str, Any]]:
        import akshare as ak

        df = ak.stock_gpzy_pledge_ratio_em(date=trade_date)
        if df is None or df.empty:
            return []
        return df.to_dict("records")

    return await self._run_sync(_fetch)
```

**New method 2 -- `get_equity_pledge_ratio_detail`** (follows same pattern):
```python
async def get_equity_pledge_ratio_detail(self) -> list[dict[str, Any]]:
    """Fetch important shareholder equity pledge details (current, full market).

    Wraps AKShare ``stock_gpzy_pledge_ratio_detail_em()``. Returns ALL
    shareholder pledge records across the entire market.

    Returns:
        List of dicts with Chinese field names.
    """
    def _fetch() -> list[dict[str, Any]]:
        import akshare as ak

        df = ak.stock_gpzy_pledge_ratio_detail_em()
        if df is None or df.empty:
            return []
        return df.to_dict("records")

    return await self._run_sync(_fetch)
```

---

### `stockvaluefinder/external/data_service.py` (MODIFY -- add pledge facade methods)

**Analog:** `stockvaluefinder/external/data_service.py` `get_buyback_data()` (lines 1752-1856)

This is the primary pattern. The `get_buyback_data()` method demonstrates the exact bulk-cache-filter pattern required for both pledge methods.

**Initialization guard** (lines 1777-1780):
```python
if not self._initialized:
    raise ExternalAPIError(
        "Data service not initialized. Call initialize() first."
    )
```

**Bulk-cache-filter pattern** (lines 1782-1796):
```python
async def _fetch() -> list[dict[str, Any]]:
    if self._akshare is None:
        raise ExternalAPIError("AKShare client is not initialized")
    return await self._akshare.get_repurchase_data()

result = await self._cache_get_or_set(
    key_parts=("buyback_full_dataset",),
    ttl=86400,
    fetch_fn=_fetch,
)
full_dataset = self._unwrap_cached_value(result)

# Filter for requested ticker (6-digit code)
symbol = ticker.split(".")[0] if "." in ticker else ticker
matching = [r for r in full_dataset if r.get("股票代码") == symbol]
```

**New method `get_equity_pledge_snapshot`** (adapts `get_buyback_data` pattern):
- Cache key: `("equity_pledge", "ratio", trade_date)` -- parameterized by date, not ticker
- TTL: 86400 (24h)
- Date discovery: `_find_latest_pledge_date()` tries last 10 calendar days
- Missing ticker from non-empty bulk = zero-pledge snapshot (per D-08)
- Empty bulk = UNAVAILABLE freshness (per D-09)

**New method `get_equity_pledge_details`** (adapts `get_buyback_data` pattern):
- Cache key: `("equity_pledge", "ratio_detail", "latest")` -- single key for current snapshot
- TTL: 86400 (24h)
- Returns `list[EquityPledgeDetail]` filtered by ticker

**New private method `_find_latest_pledge_date`** (DATA-06):
```python
async def _find_latest_pledge_date(self) -> str | None:
    """Try last 10 calendar days in reverse order to find latest with data."""
    today = date.today()
    for i in range(10):
        candidate = today - timedelta(days=i)
        date_str = candidate.strftime("%Y%m%d")
        try:
            if self._akshare is None:
                continue
            data = await self._akshare.get_equity_pledge_ratio_by_date(date_str)
            if data:
                return date_str
        except ExternalAPIError:
            logger.warning(f"Pledge data fetch failed for date {date_str}, trying previous day")
            continue
    logger.warning("No pledge data found in last 10 calendar days")
    return None
```

**Field mapping helpers** (private methods following the field map dicts from RESEARCH.md):
```python
PLEDGE_RATIO_FIELD_MAP = {
    "股票代码": "code_6digit",
    "股票简称": "stock_name",
    "交易日期": "latest_date",
    "所属行业": "industry",
    "质押比例": "company_pledge_ratio",
    "质押股数": "pledged_shares",
    "质押市值": "pledge_market_value",
    "质押笔数": "pledge_count",
    "无限售股质押数": "unrestricted_pledged_shares",
    "限售股质押数": "restricted_pledged_shares",
    "近一年涨跌幅": "one_year_price_change",
}
```

---

### `tests/unit/test_utils/test_validators.py` (MODIFY -- add TestNormalizeAShareTicker class)

**Analog:** `tests/unit/test_utils/test_validators.py` `TestValidateTickerFormat` class (lines 17-50)

Follow the existing class-based pytest pattern: class per function, descriptive test names, cover valid/invalid/edge cases.

**Existing test class pattern** (lines 17-50):
```python
class TestValidateTickerFormat:
    """Tests for validate_ticker_format function."""

    def test_normalizes_lowercase_to_uppercase(self) -> None:
        """validate_ticker_format should normalize lowercase SH to uppercase."""
        assert validate_ticker_format("600519.sh") == "600519.SH"

    def test_already_uppercase_passthrough(self) -> None:
        """validate_ticker_format should accept already-uppercase ticker."""
        assert validate_ticker_format("600519.SH") == "600519.SH"

    def test_invalid_format_raises_value_error(self) -> None:
        """validate_ticker_format should raise ValueError for non-matching format."""
        with pytest.raises(ValueError, match="Invalid ticker format"):
            validate_ticker_format("INVALID")
```

**New test class to add** (follow same style):
```python
class TestNormalizeAShareTicker:
    """Tests for normalize_a_share_ticker function."""

    def test_shanghai_main_board(self) -> None:
        """6xx codes should return .SH suffix."""
        assert normalize_a_share_ticker("600519") == "600519.SH"

    def test_shenzhen_main_board(self) -> None:
        """0xx codes should return .SZ suffix."""
        assert normalize_a_share_ticker("000002") == "000002.SZ"

    def test_chinext_board(self) -> None:
        """3xx codes should return .SZ suffix."""
        assert normalize_a_share_ticker("300001") == "300001.SZ"

    def test_bse_rejected(self) -> None:
        """8xx codes (BSE) should return None."""
        assert normalize_a_share_ticker("830001") is None

    def test_another_bse_rejected(self) -> None:
        """4xx codes (BSE) should return None."""
        assert normalize_a_share_ticker("430001") is None

    def test_invalid_prefix_returns_none(self) -> None:
        """999999 should return None (invalid prefix)."""
        assert normalize_a_share_ticker("999999") is None

    def test_non_numeric_returns_none(self) -> None:
        """Non-numeric strings should return None."""
        assert normalize_a_share_ticker("ABCDEF") is None

    def test_short_code_returns_none(self) -> None:
        """5-digit codes should return None."""
        assert normalize_a_share_ticker("60051") is None

    def test_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace should be stripped."""
        assert normalize_a_share_ticker("  600519  ") == "600519.SH"
```

---

### `tests/unit/test_models/test_equity_pledge.py` (NEW -- test, request-response)

**Analog:** `tests/unit/test_utils/test_validators.py` class-based pattern (no existing Pydantic model test file found)

Test Pydantic model construction, validation, frozen enforcement, and edge cases.

**Pattern:**
```python
"""Unit tests for equity pledge Pydantic models."""

import pytest
from datetime import date
from decimal import Decimal

from stockvaluefinder.models.equity_pledge import (
    DataFreshness,
    EquityPledgeDataQuality,
    EquityPledgeSnapshot,
    EquityPledgeDetail,
)


class TestEquityPledgeSnapshot:
    """Tests for EquityPledgeSnapshot model."""

    def test_create_with_required_fields(self) -> None:
        """Should create with required fields only."""
        ...

    def test_frozen_model_raises_on_mutation(self) -> None:
        """Frozen model should raise ValidationError on field assignment."""
        ...

    def test_zero_pledge_snapshot(self) -> None:
        """Should accept all-zero fields for zero-pledge stocks."""
        ...

    def test_company_pledge_ratio_is_percentage(self) -> None:
        """Ratio should be stored as percentage (e.g., 35.5 means 35.5%)."""
        ...
```

---

### `tests/unit/test_external/test_akshare_equity_pledge.py` (NEW -- test, request-response)

**Analog:** `tests/unit/test_external/test_akshare_client.py` (lines 1-229)

Follow the exact mock setup pattern: `mocker.MagicMock()` for AKShare, `mocker.patch.dict("sys.modules", {"akshare": mock_ak})`, `pd.DataFrame` for return values.

**Existing test pattern** (lines 44-61):
```python
@pytest.mark.asyncio
class TestAKShareClient:
    """Test suite for AKShare client functionality."""

    async def test_get_stock_info_a_success(self, mocker):
        """Test successful A-share stock info retrieval."""
        mock_ak = mocker.MagicMock()
        mock_df = pd.DataFrame([{"symbol": "600519", "name": "贵州茅台"}])

        mock_ak.stock_individual_info_em.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        result = await client.get_stock_info_a("600519")
        assert isinstance(result, list)
        assert len(result) > 0
```

**New test file pattern:**
```python
"""Unit tests for AKShare client equity pledge methods."""

import pandas as pd
import pytest

from stockvaluefinder.external.akshare_client import AKShareClient
from stockvaluefinder.utils.errors import ExternalAPIError


@pytest.mark.asyncio
class TestEquityPledgeRatioByDate:
    """Tests for get_equity_pledge_ratio_by_date."""

    async def test_returns_list_of_dicts(self, mocker) -> None:
        mock_ak = mocker.MagicMock()
        mock_df = pd.DataFrame([
            {"股票代码": "600519", "股票简称": "贵州茅台", "质押比例": 35.5},
        ])
        mock_ak.stock_gpzy_pledge_ratio_em.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        result = await client.get_equity_pledge_ratio_by_date("20240605")
        assert isinstance(result, list)
        assert len(result) == 1
        mock_ak.stock_gpzy_pledge_ratio_em.assert_called_once_with(date="20240605")

    async def test_empty_dataframe_returns_empty_list(self, mocker) -> None:
        mock_ak = mocker.MagicMock()
        mock_ak.stock_gpzy_pledge_ratio_em.return_value = pd.DataFrame()
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
        mock_ak = mocker.MagicMock()
        mock_df = pd.DataFrame([
            {"股票代码": "600519", "股东名称": "XX投资", "质押股份数量": 1000000},
        ])
        mock_ak.stock_gpzy_pledge_ratio_detail_em.return_value = mock_df
        mocker.patch("importlib.util.find_spec", return_value=True)
        mocker.patch.dict("sys.modules", {"akshare": mock_ak})

        client = AKShareClient()
        await client.check_available()

        result = await client.get_equity_pledge_ratio_detail()
        assert isinstance(result, list)
        assert len(result) == 1
```

---

### `tests/unit/test_external/test_data_service_pledge.py` (NEW -- test, request-response)

**Analog:** `tests/unit/test_external/test_data_service_cache.py` (lines 1-464)

Follow the exact `_make_mock_cache()` / `_make_service_with_cache()` helper pattern and async mock setup.

**Test helper pattern** (from lines 13-47):
```python
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
```

**Test structure** -- three test classes:
1. `TestEquityPledgeSnapshot` -- tests bulk-cache-filter, zero-pledge handling, UNAVAILABLE case
2. `TestEquityPledgeDetails` -- tests detail bulk-cache-filter
3. `TestDateDiscovery` -- tests `_find_latest_pledge_date` 10-day backfill

```python
@pytest.mark.asyncio
class TestEquityPledgeSnapshot:
    """Tests for get_equity_pledge_snapshot method."""

    async def test_cache_hit_returns_filtered_data(self) -> None:
        """Cache hit with matching ticker returns pledge data."""
        ...

    async def test_zero_pledge_when_ticker_absent_from_nonempty_bulk(self) -> None:
        """Missing ticker in non-empty bulk = zero-pledge snapshot (D-08)."""
        ...

    async def test_unavailable_when_bulk_empty(self) -> None:
        """Empty bulk response = UNAVAILABLE freshness (D-09)."""
        ...

    async def test_cache_key_includes_trade_date(self) -> None:
        """Cache key should be parameterized by trade date."""
        ...


@pytest.mark.asyncio
class TestDateDiscovery:
    """Tests for _find_latest_pledge_date method."""

    async def test_returns_first_valid_date(self, mocker) -> None:
        """Should return first date that returns non-empty data."""
        ...

    async def test_returns_none_when_all_dates_fail(self, mocker) -> None:
        """Should return None when all 10 dates return empty data."""
        ...

    async def test_skips_api_errors(self, mocker) -> None:
        """Should continue to next date on ExternalAPIError."""
        ...
```

---

## Shared Patterns

### Error Wrapping (AKShare -> ExternalAPIError)

**Source:** `stockvaluefinder/external/akshare_client.py` `_run_sync` method (lines 81-144)
**Apply to:** All new AKShare client methods (automatic via `_run_sync`)

```python
# The _run_sync method already handles all error wrapping.
# New methods just call `return await self._run_sync(_fetch)` and
# _run_sync wraps all exceptions into ExternalAPIError with retry logic.
```

### Cache Key Construction

**Source:** `stockvaluefinder/utils/cache.py` `build_cache_key` (lines 173-191)
**Apply to:** All data_service pledge methods

```python
# Convention: version:prefix:part1:part2
# Example pledge keys:
#   v1:equity_pledge:ratio:20240605       (ratio data by trade date)
#   v1:equity_pledge:ratio_detail:latest  (detail data, single key)
```

### NaN-to-None Normalization

**Source:** `stockvaluefinder/external/data_service.py` `get_buyback_data` (lines 1830-1848)
**Apply to:** All pledge field extraction from AKShare data

```python
# AKShare DataFrames often contain NaN values. When extracting float fields,
# always normalize NaN to None:
raw_value = record.get("质押比例")
if raw_value is not None:
    try:
        val = float(raw_value)
        if val == val:  # NaN check (NaN != NaN)
            result_value = val
    except (ValueError, TypeError):
        pass
```

### Async Test Setup

**Source:** `tests/unit/test_external/test_data_service_cache.py` (lines 13-47)
**Apply to:** All new test files for data_service pledge tests

```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from stockvaluefinder.external.data_service import ExternalDataService
from stockvaluefinder.utils.cache import CacheManager


def _make_mock_cache() -> tuple[MagicMock, CacheManager]:
    mock_redis = AsyncMock()
    cache = CacheManager(redis_url="redis://localhost:6379/0")
    cache._redis = mock_redis
    cache._connected = True
    return mock_redis, cache


def _make_service_with_cache(
    cache: CacheManager | None = None,
    cache_version: str = "v1",
) -> ExternalDataService:
    service = ExternalDataService(
        tushare_token="",
        enable_akshare=True,
        enable_efinance=True,
        cache=cache,
        cache_version=cache_version,
    )
    service._initialized = True
    return service
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | -- | -- | All 8 files have strong existing analogs in the codebase |

## Metadata

**Analog search scope:** `stockvaluefinder/stockvaluefinder/models/`, `stockvaluefinder/stockvaluefinder/external/`, `stockvaluefinder/stockvaluefinder/utils/`, `stockvaluefinder/tests/unit/`
**Files scanned:** 12
**Pattern extraction date:** 2026-06-06
