"""Batch market data fetcher and valuation percentile calculator.

This module provides:
    - BatchDataFetcher: Async service that fetches real-time market snapshots
      for all requested tickers via a single AKShare bulk API call.
    - calculate_valuation_percentile: Pure function for computing historical
      PE/PB percentile rankings within an index peer group.

Design decisions (per Phase 27 RESEARCH):
    - Uses AKShare stock_zh_a_spot_em() for bulk A-share data (one call for
      ~5000 stocks instead of per-stock calls).
    - dividend_yield defaults to 0.0 (not available from bulk API, Pitfall 2).
    - price_vs_52w_high defaults to 1.0 (neutral, Pitfall 6).
    - ocf_positive_years defaults to 0 (filled in later, Pitfall 5).
    - Per-ticker failures are isolated and logged without aborting the batch.
"""

import asyncio
import logging
import math
from typing import Any

from scipy.stats import percentileofscore

from stockvaluefinder.market_scanner.config import MarketScannerConfig
from stockvaluefinder.market_scanner.models import ScreeningSnapshot

logger = logging.getLogger(__name__)

# Mapping from AKShare Chinese column names to English descriptions.
# Used for documentation and field lookup consistency.
AKSHARE_FIELD_MAP: dict[str, str] = {
    "代码": "code",
    "名称": "name",
    "最新价": "price",
    "涨跌幅": "change_pct",
    "换手率": "turnover",
    "市盈率-动态": "pe_ttm",
    "市净率": "pb_ratio",
    "总市值": "market_cap",
    "成交量": "volume",
}

# Minimum number of valid historical values required for percentile calculation.
MIN_PERCENTILE_DATA_POINTS = 60


def calculate_valuation_percentile(
    current_value: float,
    historical_values: list[float],
) -> float | None:
    """Calculate percentile rank of current value within historical series.

    Uses scipy.stats.percentileofscore with kind='rank' for consistent
    tie-breaking behavior. Returns None when insufficient data is available
    or when inputs contain NaN/inf or non-positive values.

    Args:
        current_value: Current PE TTM or PB ratio.
        historical_values: Historical daily PE/PB values (ideally 5 years).

    Returns:
        Percentile rank in range [0.0, 100.0] rounded to 2 decimal places,
        or None if insufficient valid data.

    Examples:
        >>> calculate_valuation_percentile(10.0, list(range(1, 61)))
        16.67
        >>> calculate_valuation_percentile(10.0, [1, 2, 3])
        None
        >>> calculate_valuation_percentile(-1.0, list(range(1, 61)))
        None
    """
    # Check current_value for NaN/inf
    if not _is_valid_float(current_value):
        return None
    if current_value <= 0:
        return None

    # Filter non-positive values from historical data
    valid_history = [v for v in historical_values if _is_valid_float(v) and v > 0]

    if len(valid_history) < MIN_PERCENTILE_DATA_POINTS:
        return None

    result = float(percentileofscore(valid_history, current_value, kind="rank"))
    return round(result, 2)


def _is_valid_float(value: float) -> bool:
    """Check if a float value is neither NaN nor inf.

    Args:
        value: Float value to check.

    Returns:
        True if the value is a finite number, False for NaN or inf.
    """
    if isinstance(value, bool):
        return False
    if not isinstance(value, int | float):
        return False
    return math.isfinite(value)


def _safe_float(value: Any) -> float | None:  # noqa: ANN401
    """Convert a value to float, returning None for invalid inputs.

    Handles None, NaN, inf, and non-numeric types gracefully. Used for
    mapping AKShare DataFrame cells which may contain various invalid values.

    Args:
        value: Any value that might be convertible to float.

    Returns:
        Float value, or None if the input is None, NaN, inf, or non-numeric.

    Examples:
        >>> _safe_float(10.5)
        10.5
        >>> _safe_float(None)
        >>> _safe_float(float('nan'))
        >>> _safe_float(float('inf'))
    """
    if value is None:
        return None
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _to_ticker_format(akshare_code: str) -> str:
    """Convert AKShare 6-digit code to project ticker format.

    AKShare returns stock codes as 6-digit strings like "600519".
    This function maps them to the project's NNNNNN.{SH|SZ} format:
        - Codes starting with 6 -> Shanghai (SH)
        - Codes starting with 0 or 3 -> Shenzhen (SZ)

    Args:
        akshare_code: 6-digit stock code from AKShare (e.g., "600519").

    Returns:
        Ticker in NNNNNN.{SH|SZ} format, or empty string for invalid codes.

    Examples:
        >>> _to_ticker_format("600519")
        '600519.SH'
        >>> _to_ticker_format("000001")
        '000001.SZ'
        >>> _to_ticker_format("abc")
        ''
    """
    code = str(akshare_code).strip()
    if len(code) != 6 or not code.isdigit():
        return ""
    if code.startswith("6"):
        return f"{code}.SH"
    if code.startswith(("0", "3")):
        return f"{code}.SZ"
    return ""


class BatchDataFetcher:
    """Async service for fetching batch market data via AKShare bulk API.

    Fetches real-time market snapshots for all requested tickers using a
    single AKShare stock_zh_a_spot_em() call. Maps Chinese column names
    to ScreeningSnapshot fields and handles per-ticker failures gracefully.

    Usage::

        fetcher = BatchDataFetcher()
        config = MarketScannerConfig()
        snapshots = await fetcher.fetch_market_snapshots(
            tickers={"600519.SH", "000858.SZ"},
            config=config,
        )
    """

    def __init__(self) -> None:
        """Initialize the fetcher with empty error tracking."""
        self._errors: dict[str, str] = {}
        self._logger = logging.getLogger(
            f"{__name__}.{self.__class__.__name__}",
        )

    @property
    def errors(self) -> dict[str, str]:
        """Return dict of ticker -> error message for failed fetches."""
        return self._errors

    async def fetch_market_snapshots(
        self,
        tickers: set[str],
        config: MarketScannerConfig,
    ) -> dict[str, ScreeningSnapshot]:
        """Fetch market snapshots for requested tickers using bulk AKShare API.

        Makes a single stock_zh_a_spot_em() call for all A-shares, then
        filters to the requested tickers. Per-ticker failures are logged
        and recorded in self._errors without aborting the batch.

        Args:
            tickers: Set of ticker strings in NNNNNN.{SH|SZ} format.
            config: Scanner configuration (used for reference, not
                directly consumed by the fetch method).

        Returns:
            Dict mapping ticker -> ScreeningSnapshot for successfully
            fetched tickers. Failed tickers are recorded in self.errors.
        """
        # Lazy import of akshare, matching pattern in akshare_client.py
        import akshare as ak  # type: ignore[import-untyped]

        import pandas as pd  # type: ignore[import-untyped]

        self._errors = {}

        # Single bulk call -- returns DataFrame with all A-shares
        df: pd.DataFrame = await asyncio.to_thread(ak.stock_zh_a_spot_em)

        if df is None or df.empty:
            self._logger.warning("AKShare stock_zh_a_spot_em returned empty data")
            return {}

        # Map 6-digit AKShare codes to project ticker format
        df = df.copy()
        df["_ticker"] = df["代码"].apply(_to_ticker_format)

        # Filter to requested tickers
        filtered = df[df["_ticker"].isin(tickers)]

        snapshots: dict[str, ScreeningSnapshot] = {}
        for _, row in filtered.iterrows():
            ticker = str(row["_ticker"])
            if not ticker:
                continue
            try:
                # Extract fields from AKShare Chinese column names
                name = str(row.get("名称", ""))
                price_raw = row.get("最新价", 0)
                turnover_raw = row.get("换手率", 0)
                volume_raw = row.get("成交量", 0)
                market_cap_raw = row.get("总市值", 0)

                # Compute derived fields
                is_st = "st" in name.lower()
                turnover_val = float(turnover_raw) if turnover_raw else 0.0
                volume_val = float(volume_raw) if volume_raw else 0.0
                is_suspended = turnover_val == 0.0 and volume_val == 0.0
                price_val = float(price_raw) if price_raw else 0.0
                has_price_data = price_val > 0.0
                market_cap_val = float(market_cap_raw) if market_cap_raw else 0.0

                # Skip stocks with zero market cap (ScreeningSnapshot requires gt=0)
                if market_cap_val <= 0:
                    self._errors[ticker] = "Market cap is zero or negative"
                    continue

                snapshot = ScreeningSnapshot(
                    ticker=ticker,
                    name=name,
                    index_code="",  # filled by caller
                    is_st=is_st,
                    is_suspended=is_suspended,
                    has_price_data=has_price_data,
                    turnover_ratio=turnover_val,
                    pe_ttm=_safe_float(row.get("市盈率-动态")),
                    pb_ratio=_safe_float(row.get("市净率")),
                    dividend_yield=0.0,  # not available from bulk API (Pitfall 2)
                    price_vs_52w_high=1.0,  # neutral default (Pitfall 6)
                    ocf_positive_years=0,  # filled from financial data (Pitfall 5)
                    market_cap=market_cap_val,
                )
                snapshots[ticker] = snapshot
            except Exception as e:
                self._logger.warning(f"Failed to build snapshot for {ticker}: {e}")
                self._errors[ticker] = str(e)

        return snapshots
