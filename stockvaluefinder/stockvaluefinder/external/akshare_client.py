"""AKShare API client as backup data source."""

# type: ignore[import-untyped]
# mypy: ignore-errors

import logging
from datetime import date
from typing import Any, Callable


from stockvaluefinder.utils.errors import DataValidationError, ExternalAPIError

logger = logging.getLogger(__name__)


def eastmoney_hsf10_symbol(ts_code: str) -> str:
    """Convert ticker to AKShare East Money HSF10 ``symbol`` (e.g. SH600519, SZ000001).

    ``stock_*_by_report_em`` require this form; bare 6-digit codes break HTML lookup
    (``NoneType`` when parsing company type).
    """
    s = ts_code.strip().upper()
    if "." in s:
        code, mkt = s.split(".", 1)
        if mkt == "SH":
            return f"SH{code}"
        if mkt == "SZ":
            return f"SZ{code}"
        if mkt == "HK":
            return f"HK{code.zfill(5)}"
    if s.startswith(("SH", "SZ", "HK")):
        return s
    # Bare 6-digit A-share code
    if len(s) == 6 and s.isdigit():
        if s.startswith("6"):
            return f"SH{s}"
        if s.startswith(("0", "3")):
            return f"SZ{s}"
    return s


class AKShareClient:
    """Async client for AKShare API as backup data source.

    Note: AKShare is primarily a synchronous library. This client provides
    an async interface that calls AKShare functions in thread pool.
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 5,
    ) -> None:
        """Initialize AKShare client.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self._available = False
        self._last_request_time: float = 0.0

    async def check_available(self) -> bool:
        """Check if AKShare library is available.

        Returns:
            True if AKShare is available, False otherwise
        """
        try:
            import importlib.util

            spec = importlib.util.find_spec("akshare")
            self._available = spec is not None
            return self._available
        except Exception as e:
            logger.warning(f"Failed to check AKShare availability: {e}")
            return False

    async def _run_sync(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Run synchronous function in thread pool.

        Args:
            func: Synchronous function to run
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function return value

        Raises:
            ExternalAPIError: If function execution fails
        """
        import asyncio
        import random
        import time
        from concurrent.futures import ThreadPoolExecutor

        if not self._available:
            raise ExternalAPIError("AKShare library is not available")

        # Rate-limit: ensure at least 0.5s between requests to avoid
        # triggering East Money's connection-drop behaviour.
        min_interval = 0.5
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)

        last_error: Exception | None = None
        backoff_times = [2, 4, 8, 16, 30]

        for attempt in range(self.max_retries):
            try:
                self._last_request_time = time.monotonic()
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor() as pool:
                    result = await loop.run_in_executor(
                        pool,
                        lambda: func(*args, **kwargs),
                    )
                return result

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    base_wait = backoff_times[min(attempt, len(backoff_times) - 1)]
                    jitter = random.uniform(0, base_wait * 0.25)
                    wait_time = base_wait + jitter
                    logger.warning(
                        f"AKShare function error (attempt {attempt + 1}/{self.max_retries}), "
                        f"retrying in {wait_time:.1f}s: {e}"
                    )
                    await asyncio.sleep(wait_time)

        raise ExternalAPIError(
            f"AKShare function failed after {self.max_retries} attempts: {last_error}"
        ) from last_error

    async def get_stock_info_a(
        self,
        symbol: str,
    ) -> list[dict[str, Any]]:
        """Get A-share stock basic information.

        Args:
            symbol: Stock symbol (e.g., '600519')

        Returns:
            List of stock information
        """

        def _fetch() -> list[dict[str, Any]]:
            import akshare as ak  # type: ignore[import-untyped]

            df = ak.stock_individual_info_em(symbol=symbol)
            if df is None or df.empty:
                return []
            return df.to_dict("records")  # type: ignore[no-any-return]

        return await self._run_sync(_fetch)  # type: ignore[no-any-return]

    async def get_stock_info_hk(
        self,
        symbol: str,
    ) -> list[dict[str, Any]]:
        """Get Hong Kong stock information.

        Args:
            symbol: Stock symbol (e.g., '00700')

        Returns:
            List of stock information
        """

        def _fetch() -> list[dict[str, Any]]:
            import akshare as ak

            df = ak.stock_hk_spot_em()
            if df is None or df.empty:
                return []
            return df.to_dict("records")

        return await self._run_sync(_fetch)

    async def get_stock_daily(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        adjust: str = "",
    ) -> list[dict[str, Any]]:
        """Get daily market data.

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            adjust: Adjustment type ('' for no adjustment, 'qfq' for forward, 'hfq' for backward)

        Returns:
            List of daily market data
        """

        def _fetch() -> list[dict[str, Any]]:
            import akshare as ak

            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust=adjust,
            )
            if df is None or df.empty:
                return []
            return df.to_dict("records")

        return await self._run_sync(_fetch)

    async def get_dividend_by_year(
        self,
        symbol: str,
        year: int,
    ) -> list[dict[str, Any]]:
        """Get dividend data by year.

        Args:
            symbol: Stock symbol (e.g. ``600519`` — six digits for Sina)
            year: Calendar year to filter (uses 公告日期)

        Returns:
            List of dividend data
        """

        def _fetch() -> list[dict[str, Any]]:
            import akshare as ak
            import pandas as pd

            # stock_history_dividend() no longer takes symbol; use per-stock detail
            df = ak.stock_history_dividend_detail(symbol=symbol, indicator="分红")
            if df is None or df.empty:
                return []
            if "公告日期" in df.columns:
                dt = pd.to_datetime(df["公告日期"], errors="coerce")
                df = df[dt.dt.year == year]
            elif "年度" in df.columns:
                df = df[df["年度"] == str(year)]
            if df is None or df.empty:
                return []
            return df.to_dict("records")

        return await self._run_sync(_fetch)

    async def get_dividend_history(self, symbol: str) -> list[dict[str, Any]]:
        """Get dividend history detail for a single stock (Sina).

        Returns rows with columns like 公告日期 / 派息 / 送股 / 转增 / 除权除息日.
        """

        def _fetch() -> list[dict[str, Any]]:
            import akshare as ak

            df = ak.stock_history_dividend_detail(symbol=symbol, indicator="分红")
            if df is None or df.empty:
                return []
            return df.to_dict("records")

        return await self._run_sync(_fetch)

    async def get_profit_sheet(
        self,
        ts_code: str,
        period: str = "20231231",
    ) -> list[dict[str, Any]]:
        """Get income statement (profit sheet) data.

        Args:
            ts_code: Stock code (e.g. ``600519.SH`` or ``600519``)
            period: Period in YYYYMMDD format (default: latest annual)

        Returns:
            List of income statement data
        """

        def _fetch() -> list[dict[str, Any]]:
            import akshare as ak

            em = eastmoney_hsf10_symbol(ts_code)
            df = ak.stock_profit_sheet_by_report_em(symbol=em)
            if df is None or df.empty:
                return []
            if period and "REPORT_DATE" in df.columns:
                col = df["REPORT_DATE"].astype(str)
                if len(period) == 8:
                    dashed = f"{period[:4]}-{period[4:6]}-{period[6:8]}"
                    nodash = col.str.replace(r"[^\d]", "", regex=True)
                    filtered = df[
                        nodash.str.contains(period, regex=False)
                        | col.str.contains(dashed, regex=False)
                    ]
                    df = filtered if not filtered.empty else df
                else:
                    filtered = df[col == period]
                    df = filtered if not filtered.empty else df
            return df.to_dict("records")

        return await self._run_sync(_fetch)

    async def get_balance_sheet(
        self,
        ts_code: str,
        period: str = "20231231",
    ) -> list[dict[str, Any]]:
        """Get balance sheet data.

        Args:
            ts_code: Stock code (e.g. ``600519.SH`` or ``600519``)
            period: Period in YYYYMMDD format (default: latest annual)

        Returns:
            List of balance sheet data
        """

        def _fetch() -> list[dict[str, Any]]:
            import akshare as ak

            em = eastmoney_hsf10_symbol(ts_code)
            df = ak.stock_balance_sheet_by_report_em(symbol=em)
            if df is None or df.empty:
                return []
            if period and "REPORT_DATE" in df.columns:
                col = df["REPORT_DATE"].astype(str)
                if len(period) == 8:
                    dashed = f"{period[:4]}-{period[4:6]}-{period[6:8]}"
                    nodash = col.str.replace(r"[^\d]", "", regex=True)
                    filtered = df[
                        nodash.str.contains(period, regex=False)
                        | col.str.contains(dashed, regex=False)
                    ]
                    df = filtered if not filtered.empty else df
                else:
                    filtered = df[col == period]
                    df = filtered if not filtered.empty else df
            return df.to_dict("records")

        return await self._run_sync(_fetch)

    async def get_cash_flow_sheet(
        self,
        ts_code: str,
        period: str = "20231231",
    ) -> list[dict[str, Any]]:
        """Get cash flow statement data.

        Args:
            ts_code: Stock code (e.g. ``600519.SH`` or ``600519``)
            period: Period in YYYYMMDD format (default: latest annual)

        Returns:
            List of cash flow statement data
        """

        def _fetch() -> list[dict[str, Any]]:
            import akshare as ak

            em = eastmoney_hsf10_symbol(ts_code)
            df = ak.stock_cash_flow_sheet_by_report_em(symbol=em)
            if df is None or df.empty:
                return []
            if period and "REPORT_DATE" in df.columns:
                col = df["REPORT_DATE"].astype(str)
                if len(period) == 8:
                    dashed = f"{period[:4]}-{period[4:6]}-{period[6:8]}"
                    nodash = col.str.replace(r"[^\d]", "", regex=True)
                    filtered = df[
                        nodash.str.contains(period, regex=False)
                        | col.str.contains(dashed, regex=False)
                    ]
                    df = filtered if not filtered.empty else df
                else:
                    filtered = df[col == period]
                    df = filtered if not filtered.empty else df
            return df.to_dict("records")

        return await self._run_sync(_fetch)

    async def get_shares_outstanding(self, symbol: str) -> float:
        """Get total shares outstanding via stock_individual_info_em.

        Args:
            symbol: Stock symbol (e.g., '600519')

        Returns:
            Total shares outstanding (in shares)

        Raises:
            ExternalAPIError: If AKShare call fails
            DataValidationError: If shares data not found
        """

        def _fetch() -> float:
            import akshare as ak

            df = ak.stock_individual_info_em(symbol=symbol)
            if df is None or df.empty:
                raise DataValidationError(f"No stock info returned for {symbol}")
            # df has columns: item, value
            row = df[df["item"] == "总股本"]
            if row.empty:
                raise DataValidationError(
                    f"总股本 not found in stock info for {symbol}"
                )
            total_shares = float(row.iloc[0]["value"])
            if total_shares <= 0:
                raise DataValidationError(
                    f"Invalid shares outstanding for {symbol}: {total_shares}"
                )
            return total_shares

        return await self._run_sync(_fetch)
