"""Unit tests for batch_data_fetcher module.

Tests cover:
    - calculate_valuation_percentile: pure function for PE/PB percentile
    - _safe_float: NaN/inf/None handling for AKShare data
    - _to_ticker_format: AKShare code to project ticker mapping
    - BatchDataFetcher: async batch market data fetching with ST detection,
      suspension detection, zero market cap skipping, and failure isolation
"""

from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from stockvaluefinder.market_scanner.batch_data_fetcher import (
    BatchDataFetcher,
    _safe_float,
    _to_ticker_format,
    calculate_valuation_percentile,
)
from stockvaluefinder.market_scanner.config import MarketScannerConfig
from stockvaluefinder.market_scanner.models import ScreeningSnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spot_df(tickers_data: list[dict]) -> pd.DataFrame:
    """Build mock DataFrame matching AKShare stock_zh_a_spot_em() output.

    Each dict in tickers_data should have keys matching AKShare Chinese
    column names: 代码, 名称, 最新价, 换手率, 市盈率-动态, 市净率, 总市值, 成交量.
    """
    columns = ["代码", "名称", "最新价", "换手率", "市盈率-动态", "市净率", "总市值", "成交量"]
    rows = []
    for td in tickers_data:
        row = {col: td.get(col, 0) for col in columns}
        rows.append(row)
    return pd.DataFrame(rows, columns=columns)


def _default_config() -> MarketScannerConfig:
    """Return a default MarketScannerConfig."""
    return MarketScannerConfig()


# ---------------------------------------------------------------------------
# Test calculate_valuation_percentile
# ---------------------------------------------------------------------------


class TestPercentileBasic:
    """Basic percentile calculation with sufficient data."""

    def test_percentile_basic(self) -> None:
        """Returns a float percentile when given 60+ valid historical values."""
        history = [5, 8, 10, 12, 15, 20] * 10  # 60 values
        result = calculate_valuation_percentile(10.0, history)
        assert result is not None
        assert isinstance(result, float)

    def test_percentile_returns_value_in_range(self) -> None:
        """Percentile result should be between 0 and 100."""
        history = list(range(1, 61))  # 60 values
        result = calculate_valuation_percentile(30.0, history)
        assert result is not None
        assert 0.0 <= result <= 100.0


class TestPercentileInsufficientData:
    """Returns None when fewer than 60 valid historical values."""

    def test_percentile_returns_none_insufficient_data(self) -> None:
        """Fewer than 60 historical values returns None."""
        result = calculate_valuation_percentile(10.0, [1, 2, 3, 4, 5])
        assert result is None

    def test_percentile_returns_none_empty_history(self) -> None:
        """Empty history returns None."""
        result = calculate_valuation_percentile(10.0, [])
        assert result is None


class TestPercentileNonPositiveCurrent:
    """Returns None when current value is non-positive."""

    def test_percentile_returns_none_nonpositive_current(self) -> None:
        """Negative current value returns None."""
        history = [5, 8, 10, 12, 15, 20] * 10  # 60 values
        result = calculate_valuation_percentile(-1.0, history)
        assert result is None

    def test_percentile_returns_none_zero_current(self) -> None:
        """Zero current value returns None."""
        history = [5, 8, 10, 12, 15, 20] * 10
        result = calculate_valuation_percentile(0.0, history)
        assert result is None


class TestPercentileFiltersHistory:
    """Filters non-positive values from historical data before computing."""

    def test_percentile_filters_nonpositive_history(self) -> None:
        """Historical values <= 0 are filtered out before computing percentile."""
        # 55 positive + 5 negative = 60 total, but only 55 valid -> None
        history = [5, 8, 10, 12, 15, 20] * 10  # 60 positive
        history_with_neg = history + [-1, -2, -3, -4, -5]
        result = calculate_valuation_percentile(10.0, history_with_neg)
        # 60 positive values remain after filtering -> should return a value
        assert result is not None

    def test_percentile_too_few_after_filter(self) -> None:
        """If filtering leaves fewer than 60 valid values, returns None."""
        # 50 positive + 10 negative = 60 total, but only 50 valid -> None
        history = [float(i) for i in range(1, 51)] + [-1.0] * 10
        result = calculate_valuation_percentile(10.0, history)
        assert result is None


class TestPercentileHandlesNaN:
    """Handles NaN/inf in current_value by returning None."""

    def test_percentile_handles_nan_current(self) -> None:
        """NaN current value returns None."""
        result = calculate_valuation_percentile(float("nan"), [1.0] * 60)
        assert result is None

    def test_percentile_handles_inf_current(self) -> None:
        """Inf current value returns None."""
        result = calculate_valuation_percentile(float("inf"), [1.0] * 60)
        assert result is None

    def test_percentile_handles_nan_in_history(self) -> None:
        """NaN values in history are filtered out."""
        history = [5.0, 8.0, 10.0, 12.0, 15.0, 20.0] * 10  # 60 valid
        history_with_nan = history + [float("nan")] * 5  # added NaN values
        result = calculate_valuation_percentile(10.0, history_with_nan)
        # 60 valid values remain -> should return a value
        assert result is not None


class TestPercentileRounding:
    """Result is rounded to 2 decimal places."""

    def test_percentile_rounded_to_2dp(self) -> None:
        """Result should be rounded to 2 decimal places."""
        history = list(range(1, 61))
        result = calculate_valuation_percentile(30.5, history)
        if result is not None:
            assert result == round(result, 2)


# ---------------------------------------------------------------------------
# Test _to_ticker_format
# ---------------------------------------------------------------------------


class TestToTickerFormat:
    """Convert AKShare 6-digit codes to project ticker format."""

    def test_to_ticker_format_sh(self) -> None:
        """Code starting with 6 maps to .SH."""
        assert _to_ticker_format("600519") == "600519.SH"

    def test_to_ticker_format_sz(self) -> None:
        """Code starting with 0 maps to .SZ."""
        assert _to_ticker_format("000001") == "000001.SZ"

    def test_to_ticker_format_sz_3(self) -> None:
        """Code starting with 3 maps to .SZ."""
        assert _to_ticker_format("300001") == "300001.SZ"

    def test_to_ticker_format_invalid(self) -> None:
        """Non-6-digit code returns empty string."""
        assert _to_ticker_format("abc") == ""

    def test_to_ticker_format_short(self) -> None:
        """Short code returns empty string."""
        assert _to_ticker_format("60051") == ""

    def test_to_ticker_format_long(self) -> None:
        """Too-long code returns empty string."""
        assert _to_ticker_format("6005199") == ""

    def test_to_ticker_format_non_digit_start_4(self) -> None:
        """Code starting with 4 (not 6, 0, 3) returns empty string."""
        assert _to_ticker_format("400001") == ""


# ---------------------------------------------------------------------------
# Test _safe_float
# ---------------------------------------------------------------------------


class TestSafeFloat:
    """Safe float conversion for AKShare data cells."""

    def test_safe_float_normal(self) -> None:
        """Normal float value passes through."""
        assert _safe_float(10.5) == 10.5

    def test_safe_float_int(self) -> None:
        """Integer value converts to float."""
        assert _safe_float(10) == 10.0

    def test_safe_float_none(self) -> None:
        """None returns None."""
        assert _safe_float(None) is None

    def test_safe_float_nan(self) -> None:
        """NaN returns None."""
        assert _safe_float(float("nan")) is None

    def test_safe_float_inf(self) -> None:
        """Positive infinity returns None."""
        assert _safe_float(float("inf")) is None

    def test_safe_float_neg_inf(self) -> None:
        """Negative infinity returns None."""
        assert _safe_float(float("-inf")) is None

    def test_safe_float_string(self) -> None:
        """Non-numeric string returns None."""
        assert _safe_float("abc") is None

    def test_safe_float_numeric_string(self) -> None:
        """Numeric string converts to float."""
        assert _safe_float("10.5") == 10.5

    def test_safe_float_zero(self) -> None:
        """Zero returns 0.0."""
        assert _safe_float(0) == 0.0

    def test_safe_float_negative(self) -> None:
        """Negative value passes through."""
        assert _safe_float(-5.5) == -5.5


# ---------------------------------------------------------------------------
# Test BatchDataFetcher
# ---------------------------------------------------------------------------


class TestBatchDataFetcherBasic:
    """Basic batch fetch with 3 valid tickers."""

    @pytest.mark.asyncio
    async def test_fetch_market_snapshots_basic(self) -> None:
        """Returns dict with 3 ScreeningSnapshot objects for 3 valid tickers."""
        mock_df = _make_spot_df([
            {
                "代码": "600519",
                "名称": "贵州茅台",
                "最新价": 1800.0,
                "换手率": 0.5,
                "市盈率-动态": 30.0,
                "市净率": 10.0,
                "总市值": 2_260_000_000_000,
                "成交量": 50000,
            },
            {
                "代码": "000858",
                "名称": "五粮液",
                "最新价": 150.0,
                "换手率": 1.2,
                "市盈率-动态": 25.0,
                "市净率": 8.0,
                "总市值": 600_000_000_000,
                "成交量": 80000,
            },
            {
                "代码": "601318",
                "名称": "中国平安",
                "最新价": 45.0,
                "换手率": 0.8,
                "市盈率-动态": 12.0,
                "市净率": 1.5,
                "总市值": 800_000_000_000,
                "成交量": 120000,
            },
        ])

        fetcher = BatchDataFetcher()
        with patch("akshare.stock_zh_a_spot_em", return_value=mock_df):
            result = await fetcher.fetch_market_snapshots(
                tickers={"600519.SH", "000858.SZ", "601318.SH"},
                config=_default_config(),
            )

        assert len(result) == 3
        assert all(isinstance(v, ScreeningSnapshot) for v in result.values())
        assert "600519.SH" in result
        assert "000858.SZ" in result
        assert "601318.SH" in result


class TestFetchSTDetection:
    """ST status detected from stock name containing 'ST' (case-insensitive)."""

    @pytest.mark.asyncio
    async def test_fetch_snapshots_detects_st(self) -> None:
        """Stock with 'ST' in name has is_st=True."""
        mock_df = _make_spot_df([
            {
                "代码": "600519",
                "名称": "ST某某",
                "最新价": 5.0,
                "换手率": 0.5,
                "市盈率-动态": 20.0,
                "市净率": 1.0,
                "总市值": 5_000_000_000,
                "成交量": 30000,
            },
        ])

        fetcher = BatchDataFetcher()
        with patch("akshare.stock_zh_a_spot_em", return_value=mock_df):
            result = await fetcher.fetch_market_snapshots(
                tickers={"600519.SH"},
                config=_default_config(),
            )

        assert "600519.SH" in result
        assert result["600519.SH"].is_st is True

    @pytest.mark.asyncio
    async def test_fetch_snapshots_detects_st_lowercase(self) -> None:
        """Stock with 'st' in lowercase name has is_st=True."""
        mock_df = _make_spot_df([
            {
                "代码": "000001",
                "名称": "*st某某",
                "最新价": 3.0,
                "换手率": 0.5,
                "市盈率-动态": 15.0,
                "市净率": 0.5,
                "总市值": 3_000_000_000,
                "成交量": 20000,
            },
        ])

        fetcher = BatchDataFetcher()
        with patch("akshare.stock_zh_a_spot_em", return_value=mock_df):
            result = await fetcher.fetch_market_snapshots(
                tickers={"000001.SZ"},
                config=_default_config(),
            )

        assert "000001.SZ" in result
        assert result["000001.SZ"].is_st is True

    @pytest.mark.asyncio
    async def test_fetch_snapshots_no_st_normal_name(self) -> None:
        """Normal stock name has is_st=False."""
        mock_df = _make_spot_df([
            {
                "代码": "600519",
                "名称": "贵州茅台",
                "最新价": 1800.0,
                "换手率": 0.5,
                "市盈率-动态": 30.0,
                "市净率": 10.0,
                "总市值": 2_260_000_000_000,
                "成交量": 50000,
            },
        ])

        fetcher = BatchDataFetcher()
        with patch("akshare.stock_zh_a_spot_em", return_value=mock_df):
            result = await fetcher.fetch_market_snapshots(
                tickers={"600519.SH"},
                config=_default_config(),
            )

        assert result["600519.SH"].is_st is False


class TestFetchSuspensionDetection:
    """Suspended stocks detected from zero turnover and zero volume."""

    @pytest.mark.asyncio
    async def test_fetch_snapshots_detects_suspended(self) -> None:
        """Stock with turnover=0 AND volume=0 has is_suspended=True."""
        mock_df = _make_spot_df([
            {
                "代码": "600519",
                "名称": "贵州茅台",
                "最新价": 1800.0,
                "换手率": 0,
                "市盈率-动态": 30.0,
                "市净率": 10.0,
                "总市值": 2_260_000_000_000,
                "成交量": 0,
            },
        ])

        fetcher = BatchDataFetcher()
        with patch("akshare.stock_zh_a_spot_em", return_value=mock_df):
            result = await fetcher.fetch_market_snapshots(
                tickers={"600519.SH"},
                config=_default_config(),
            )

        assert result["600519.SH"].is_suspended is True

    @pytest.mark.asyncio
    async def test_fetch_snapshots_not_suspended_with_turnover(self) -> None:
        """Stock with positive turnover is not suspended."""
        mock_df = _make_spot_df([
            {
                "代码": "600519",
                "名称": "贵州茅台",
                "最新价": 1800.0,
                "换手率": 0.5,
                "市盈率-动态": 30.0,
                "市净率": 10.0,
                "总市值": 2_260_000_000_000,
                "成交量": 0,
            },
        ])

        fetcher = BatchDataFetcher()
        with patch("akshare.stock_zh_a_spot_em", return_value=mock_df):
            result = await fetcher.fetch_market_snapshots(
                tickers={"600519.SH"},
                config=_default_config(),
            )

        assert result["600519.SH"].is_suspended is False


class TestFetchZeroMarketCap:
    """Stocks with zero market cap are excluded (ScreeningSnapshot requires gt=0)."""

    @pytest.mark.asyncio
    async def test_fetch_snapshots_skips_zero_market_cap(self) -> None:
        """Row with 总市值=0 is excluded from results."""
        mock_df = _make_spot_df([
            {
                "代码": "600519",
                "名称": "贵州茅台",
                "最新价": 1800.0,
                "换手率": 0.5,
                "市盈率-动态": 30.0,
                "市净率": 10.0,
                "总市值": 0,
                "成交量": 50000,
            },
        ])

        fetcher = BatchDataFetcher()
        with patch("akshare.stock_zh_a_spot_em", return_value=mock_df):
            result = await fetcher.fetch_market_snapshots(
                tickers={"600519.SH"},
                config=_default_config(),
            )

        assert "600519.SH" not in result
        assert "600519.SH" in fetcher.errors


class TestFetchIsolatedFailure:
    """Per-ticker failures are isolated without aborting the batch."""

    @pytest.mark.asyncio
    async def test_fetch_snapshots_isolated_failure(self) -> None:
        """One row failing does not prevent other rows from being returned."""
        # Create a DataFrame where one row will cause an error
        # by having an invalid ticker code (already filtered) or bad data
        mock_df = _make_spot_df([
            {
                "代码": "600519",
                "名称": "贵州茅台",
                "最新价": 1800.0,
                "换手率": 0.5,
                "市盈率-动态": 30.0,
                "市净率": 10.0,
                "总市值": 2_260_000_000_000,
                "成交量": 50000,
            },
        ])
        # Add a row with a valid code but problematic data
        # We need to create a scenario where ScreeningSnapshot construction fails
        # The easiest way is market_cap = 0 (which gets filtered with error)
        bad_row = pd.DataFrame([{
            "代码": "000001",
            "名称": "Bad Stock",
            "最新价": "not_a_number",  # This will cause an error
            "换手率": 0.5,
            "市盈率-动态": 15.0,
            "市净率": 1.0,
            "总市值": 3_000_000_000,
            "成交量": 20000,
        }])
        mock_df = pd.concat([mock_df, bad_row], ignore_index=True)

        fetcher = BatchDataFetcher()
        with patch("akshare.stock_zh_a_spot_em", return_value=mock_df):
            result = await fetcher.fetch_market_snapshots(
                tickers={"600519.SH", "000001.SZ"},
                config=_default_config(),
            )

        # The good row should still be returned
        assert "600519.SH" in result
        # The bad row should be recorded in errors
        assert "000001.SZ" in fetcher.errors


class TestFetchPENone:
    """PE TTM is None when AKShare returns NaN or None."""

    @pytest.mark.asyncio
    async def test_fetch_snapshots_pe_none_when_negative(self) -> None:
        """Row with 市盈率-动态=None results in pe_ttm=None."""
        mock_df = _make_spot_df([
            {
                "代码": "600519",
                "名称": "贵州茅台",
                "最新价": 1800.0,
                "换手率": 0.5,
                "市盈率-动态": None,
                "市净率": 10.0,
                "总市值": 2_260_000_000_000,
                "成交量": 50000,
            },
        ])

        fetcher = BatchDataFetcher()
        with patch("akshare.stock_zh_a_spot_em", return_value=mock_df):
            result = await fetcher.fetch_market_snapshots(
                tickers={"600519.SH"},
                config=_default_config(),
            )

        assert result["600519.SH"].pe_ttm is None

    @pytest.mark.asyncio
    async def test_fetch_snapshots_pe_none_when_nan(self) -> None:
        """Row with 市盈率-动态=NaN results in pe_ttm=None."""
        mock_df = _make_spot_df([
            {
                "代码": "600519",
                "名称": "贵州茅台",
                "最新价": 1800.0,
                "换手率": 0.5,
                "市盈率-动态": float("nan"),
                "市净率": 10.0,
                "总市值": 2_260_000_000_000,
                "成交量": 50000,
            },
        ])

        fetcher = BatchDataFetcher()
        with patch("akshare.stock_zh_a_spot_em", return_value=mock_df):
            result = await fetcher.fetch_market_snapshots(
                tickers={"600519.SH"},
                config=_default_config(),
            )

        assert result["600519.SH"].pe_ttm is None


class TestFetchDefaults:
    """Verify default values for fields not available from bulk API."""

    @pytest.mark.asyncio
    async def test_fetch_snapshots_defaults(self) -> None:
        """Verify dividend_yield=0.0, price_vs_52w_high=1.0, ocf_positive_years=0."""
        mock_df = _make_spot_df([
            {
                "代码": "600519",
                "名称": "贵州茅台",
                "最新价": 1800.0,
                "换手率": 0.5,
                "市盈率-动态": 30.0,
                "市净率": 10.0,
                "总市值": 2_260_000_000_000,
                "成交量": 50000,
            },
        ])

        fetcher = BatchDataFetcher()
        with patch("akshare.stock_zh_a_spot_em", return_value=mock_df):
            result = await fetcher.fetch_market_snapshots(
                tickers={"600519.SH"},
                config=_default_config(),
            )

        snapshot = result["600519.SH"]
        assert snapshot.dividend_yield == 0.0
        assert snapshot.price_vs_52w_high == 1.0
        assert snapshot.ocf_positive_years == 0


class TestFetchEmptyResult:
    """Empty DataFrame returns empty dict."""

    @pytest.mark.asyncio
    async def test_fetch_snapshots_empty_df(self) -> None:
        """Empty DataFrame from AKShare returns empty dict."""
        mock_df = pd.DataFrame()

        fetcher = BatchDataFetcher()
        with patch("akshare.stock_zh_a_spot_em", return_value=mock_df):
            result = await fetcher.fetch_market_snapshots(
                tickers={"600519.SH"},
                config=_default_config(),
            )

        assert result == {}


class TestFetchHasPriceData:
    """has_price_data is True when latest price > 0."""

    @pytest.mark.asyncio
    async def test_fetch_has_price_data_true(self) -> None:
        """Stock with positive price has has_price_data=True."""
        mock_df = _make_spot_df([
            {
                "代码": "600519",
                "名称": "贵州茅台",
                "最新价": 1800.0,
                "换手率": 0.5,
                "市盈率-动态": 30.0,
                "市净率": 10.0,
                "总市值": 2_260_000_000_000,
                "成交量": 50000,
            },
        ])

        fetcher = BatchDataFetcher()
        with patch("akshare.stock_zh_a_spot_em", return_value=mock_df):
            result = await fetcher.fetch_market_snapshots(
                tickers={"600519.SH"},
                config=_default_config(),
            )

        assert result["600519.SH"].has_price_data is True

    @pytest.mark.asyncio
    async def test_fetch_has_price_data_false(self) -> None:
        """Stock with zero price has has_price_data=False."""
        mock_df = _make_spot_df([
            {
                "代码": "600519",
                "名称": "贵州茅台",
                "最新价": 0,
                "换手率": 0,
                "市盈率-动态": 30.0,
                "市净率": 10.0,
                "总市值": 2_260_000_000_000,
                "成交量": 0,
            },
        ])

        fetcher = BatchDataFetcher()
        with patch("akshare.stock_zh_a_spot_em", return_value=mock_df):
            result = await fetcher.fetch_market_snapshots(
                tickers={"600519.SH"},
                config=_default_config(),
            )

        assert result["600519.SH"].has_price_data is False


class TestFetchFieldMapping:
    """Verify AKShare Chinese columns map to correct ScreeningSnapshot fields."""

    @pytest.mark.asyncio
    async def test_fetch_field_mapping(self) -> None:
        """All expected fields are correctly mapped from Chinese column names."""
        mock_df = _make_spot_df([
            {
                "代码": "600519",
                "名称": "贵州茅台",
                "最新价": 1800.0,
                "换手率": 0.55,
                "市盈率-动态": 30.5,
                "市净率": 10.2,
                "总市值": 2_260_000_000_000,
                "成交量": 50000,
            },
        ])

        fetcher = BatchDataFetcher()
        with patch("akshare.stock_zh_a_spot_em", return_value=mock_df):
            result = await fetcher.fetch_market_snapshots(
                tickers={"600519.SH"},
                config=_default_config(),
            )

        snapshot = result["600519.SH"]
        assert snapshot.ticker == "600519.SH"
        assert snapshot.name == "贵州茅台"
        assert snapshot.turnover_ratio == 0.55
        assert snapshot.pe_ttm == 30.5
        assert snapshot.pb_ratio == 10.2
        assert snapshot.market_cap == 2_260_000_000_000


class TestFetcherErrorsReset:
    """Errors dict is reset on each fetch call."""

    @pytest.mark.asyncio
    async def test_errors_reset_on_new_fetch(self) -> None:
        """Errors from previous fetch are cleared on new fetch."""
        # First call: zero market cap -> error
        mock_df1 = _make_spot_df([
            {
                "代码": "600519",
                "名称": "贵州茅台",
                "最新价": 1800.0,
                "换手率": 0.5,
                "市盈率-动态": 30.0,
                "市净率": 10.0,
                "总市值": 0,
                "成交量": 50000,
            },
        ])
        fetcher = BatchDataFetcher()
        with patch("akshare.stock_zh_a_spot_em", return_value=mock_df1):
            await fetcher.fetch_market_snapshots(
                tickers={"600519.SH"},
                config=_default_config(),
            )
        assert "600519.SH" in fetcher.errors

        # Second call: valid data -> errors should be reset
        mock_df2 = _make_spot_df([
            {
                "代码": "600519",
                "名称": "贵州茅台",
                "最新价": 1800.0,
                "换手率": 0.5,
                "市盈率-动态": 30.0,
                "市净率": 10.0,
                "总市值": 2_260_000_000_000,
                "成交量": 50000,
            },
        ])
        with patch("akshare.stock_zh_a_spot_em", return_value=mock_df2):
            await fetcher.fetch_market_snapshots(
                tickers={"600519.SH"},
                config=_default_config(),
            )
        assert fetcher.errors == {}
