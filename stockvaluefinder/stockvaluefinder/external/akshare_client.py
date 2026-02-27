"""AKShare API client as backup data source."""

import logging
from datetime import date
from typing import Any


from stockvaluefinder.utils.errors import ExternalAPIError

logger = logging.getLogger(__name__)


class AKShareClient:
    """Async client for AKShare API as backup data source.

    Note: AKShare is primarily a synchronous library. This client provides
    an async interface that calls AKShare functions in thread pool.
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize AKShare client.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self._available = False

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
        func: callable,
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
            raise ExternalAPIError("AKShare library is not available")

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
                    f"AKShare function error (attempt {attempt + 1}), retrying in {wait_time}s: {e}"
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
        async def _fetch() -> list[dict[str, Any]]:
            import akshare as ak

            df = ak.stock_individual_info_em(symbol=symbol)
            return df.to_dict("records")

        return await self._run_sync(_fetch)

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
        async def _fetch() -> list[dict[str, Any]]:
            import akshare as ak

            df = ak.stock_hk_spot_em()
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
        async def _fetch() -> list[dict[str, Any]]:
            import akshare as ak

            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust=adjust,
            )
            return df.to_dict("records")

        return await self._run_sync(_fetch)

    async def get_dividend_by_year(
        self,
        symbol: str,
        year: int,
    ) -> list[dict[str, Any]]:
        """Get dividend data by year.

        Args:
            symbol: Stock symbol
            year: Year

        Returns:
            List of dividend data
        """
        async def _fetch() -> list[dict[str, Any]]:
            import akshare as ak

            df = ak.stock_dividend_by_year(symbol=symbol, year=year)
            return df.to_dict("records")

        return await self._run_sync(_fetch)
