"""efinance API client as secondary backup data source.

efinance is East Money's official open-source library for financial data.
It serves as a reliable backup when AKShare has issues.
"""

# type: ignore[import-untyped]
# mypy: ignore-errors

import logging
from datetime import date
from typing import Any, Callable

from stockvaluefinder.utils.errors import ExternalAPIError

logger = logging.getLogger(__name__)


class EFinanceClient:
    """Async client for efinance API as secondary backup data source.

    efinance is officially maintained by East Money and provides reliable
    access to Chinese stock market data including real-time quotes and
    financial statements.
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize efinance client.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self._available = False

    async def check_available(self) -> bool:
        """Check if efinance library is available.

        Returns:
            True if efinance is available, False otherwise
        """
        try:
            import importlib.util

            spec = importlib.util.find_spec("efinance")
            self._available = spec is not None
            return self._available
        except Exception as e:
            logger.warning(f"Failed to check efinance availability: {e}")
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
        from concurrent.futures import ThreadPoolExecutor

        if not self._available:
            raise ExternalAPIError("efinance library is not available")

        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor() as pool:
                    result = await loop.run_in_executor(
                        pool,
                        lambda: func(*args, **kwargs),
                    )
                return result

            except Exception as e:
                last_error = e
                wait_time = 2**attempt
                logger.warning(
                    f"efinance function error (attempt {attempt + 1}), "
                    f"retrying in {wait_time}s: {e}"
                )
                await asyncio.sleep(wait_time)

        raise ExternalAPIError(
            f"efinance function failed after {self.max_retries} attempts: {last_error}"
        ) from last_error

    async def get_stock_base_info(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """Get stock basic information.

        Args:
            symbol: Stock symbol (e.g., '600519')

        Returns:
            Dictionary with stock information
        """

        def _fetch() -> dict[str, Any]:
            import efinance as ef  # type: ignore[import-untyped]

            df = ef.stock.get_base_info(symbol)
            if df is not None and not df.empty:
                return df.iloc[0].to_dict()  # type: ignore[no-any-return]
            return {}

        return await self._run_sync(_fetch)  # type: ignore[no-any-return]

    async def get_stock_daily(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Get daily market data.

        Args:
            symbol: Stock symbol (e.g., '600519')
            start_date: Start date
            end_date: End date

        Returns:
            List of daily market data
        """

        def _fetch() -> list[dict[str, Any]]:
            import efinance as ef

            df = ef.stock.get_quote_history(
                stock_codes=symbol,
                beg=start_date.strftime("%Y%m%d"),
                end=end_date.strftime("%Y%m%d"),
                klt=1,  # 1 for daily
            )
            return df.to_dict("records") if df is not None else []

        return await self._run_sync(_fetch)

    async def get_stock_financial_analysis(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """Get financial analysis data including key ratios.

        Args:
            symbol: Stock symbol (e.g., '600519')

        Returns:
            Dictionary with financial analysis data
        """

        def _fetch() -> dict[str, Any]:
            import efinance as ef

            # Get financial indicators
            df = ef.stock.get_indicator(symbol=symbol)
            if df is not None and not df.empty:
                # Get latest data
                return df.iloc[0].to_dict()
            return {}

        return await self._run_sync(_fetch)

    async def get_profit_sheet(
        self,
        symbol: str,
        period: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get income statement (profit sheet) data.

        Args:
            symbol: Stock symbol (e.g., '600519')
            period: Period in YYYYMMDD format (optional)

        Returns:
            List of income statement data
        """
        # efinance doesn't provide financial statement APIs
        # Return empty to allow fallback to other sources
        logger.warning(
            f"efinance doesn't support profit sheet API for {symbol}. "
            "Falling back to other sources."
        )
        return []

    async def get_balance_sheet(
        self,
        symbol: str,
        period: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get balance sheet data.

        Args:
            symbol: Stock symbol (e.g., '600519')
            period: Period in YYYYMMDD format (optional)

        Returns:
            List of balance sheet data
        """
        # efinance doesn't provide financial statement APIs
        logger.warning(
            f"efinance doesn't support balance sheet API for {symbol}. "
            "Falling back to other sources."
        )
        return []

    async def get_cash_flow_sheet(
        self,
        symbol: str,
        period: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get cash flow statement data.

        Args:
            symbol: Stock symbol (e.g., '600519')
            period: Period in YYYYMMDD format (optional)

        Returns:
            List of cash flow statement data
        """
        # efinance doesn't provide financial statement APIs
        logger.warning(
            f"efinance doesn't support cash flow sheet API for {symbol}. "
            "Falling back to other sources."
        )
        return []

    async def get_realtime_quotes(
        self,
        symbols: list[str],
    ) -> list[dict[str, Any]]:
        """Get real-time stock quotes.

        Args:
            symbols: List of stock symbols

        Returns:
            List of real-time quote data
        """

        def _fetch() -> list[dict[str, Any]]:
            import efinance as ef

            df = ef.stock.get_realtime_quotes(symbols)
            return df.to_dict("records") if df is not None else []

        return await self._run_sync(_fetch)
