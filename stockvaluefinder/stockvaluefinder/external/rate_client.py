"""Interest rate fetcher for risk-free rates (treasury yields, deposit rates)."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any, Callable

import httpx

from stockvaluefinder.utils.errors import ExternalAPIError

logger = logging.getLogger(__name__)

# Fallback static rates when live API is unavailable
_STATIC_CHINA_RATES: dict[str, float] = {
    "ten_year_treasury": 0.0182,  # 1.82%
    "three_year_deposit": 0.0215,  # 2.15% (PBOC benchmark, rarely changes)
    "one_year_deposit": 0.0175,  # 1.75% (PBOC benchmark, rarely changes)
    "benchmark_rate": 0.030,  # 3.0% (1-year LPR)
}

_STATIC_HK_RATES: dict[str, float] = {
    "ten_year_treasury": 0.0415,  # 4.15%
    "three_year_deposit": 0.0400,  # 4.0%
    "one_year_deposit": 0.0450,  # 4.5%
    "benchmark_rate": 0.050,  # 5.0% (HKMA base rate)
}


async def _run_sync(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run synchronous AKShare function in thread pool."""
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(pool, lambda: func(*args, **kwargs))


class RateClient:
    """Client for fetching market interest rate data.

    Sources:
    - China 10Y treasury: AKShare bond_china_yield (China Bond Info Network)
    - China LPR: AKShare macro_china_lpr (East Money)
    - China deposit rates: Static fallback (PBOC benchmarks change infrequently)
    - Hong Kong: Static fallback (to be replaced with HKMA API)
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize rate client.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "RateClient":
        """Enter async context manager."""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(
        self,
        exc_type: type[Exception] | None,
        exc_val: Exception | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context manager."""
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        """Get HTTP client, raising error if not initialized."""
        if self._client is None:
            raise ExternalAPIError(
                "HTTP client not initialized. Use async context manager."
            )
        return self._client

    async def get_china_rates(self, rate_date: date | None = None) -> dict[str, float]:
        """Get China interest rates (treasury and deposit).

        Fetches live 10-year treasury yield from AKShare (China Bond Info Network)
        and 1-year LPR from East Money. Deposit rates fall back to PBOC benchmarks
        as they change infrequently and have no free real-time API.

        Args:
            rate_date: Date for rates (uses latest if None)

        Returns:
            Dictionary with:
                - ten_year_treasury: 10-year government bond yield
                - three_year_deposit: 3-year large deposit rate
                - one_year_deposit: 1-year deposit rate
                - benchmark_rate: 1-year LPR (Loan Prime Rate)

        Raises:
            ExternalAPIError: If rate fetching fails
        """
        rates = dict(_STATIC_CHINA_RATES)

        try:
            treasury_rate = await self._fetch_china_treasury_10y(rate_date)
            if treasury_rate is not None:
                rates["ten_year_treasury"] = treasury_rate
        except Exception as e:
            logger.warning(
                f"Failed to fetch live 10Y treasury yield, using fallback: {e}"
            )

        try:
            lpr = await self._fetch_china_lpr_1y()
            if lpr is not None:
                rates["benchmark_rate"] = lpr
        except Exception as e:
            logger.warning(f"Failed to fetch live LPR, using fallback: {e}")

        logger.info(
            "China rates: 10Y=%.4f, 3Y_deposit=%.4f, 1Y_deposit=%.4f, LPR=%.4f",
            rates["ten_year_treasury"],
            rates["three_year_deposit"],
            rates["one_year_deposit"],
            rates["benchmark_rate"],
        )
        return rates

    async def _fetch_china_treasury_10y(
        self, rate_date: date | None = None
    ) -> float | None:
        """Fetch 10-year government bond yield from AKShare.

        Uses bond_china_yield which returns data from China Bond Information Network.
        Filters for '中债国债收益率曲线' to get the sovereign yield curve.

        Args:
            rate_date: Target date (defaults to latest available)

        Returns:
            10-year yield as decimal (e.g. 0.0182 for 1.82%), or None on failure
        """

        def _fetch() -> float | None:
            import akshare as ak  # type: ignore[import-untyped]

            end = rate_date or date.today()
            start = end - timedelta(days=7)
            df = ak.bond_china_yield(
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )
            if df is None or df.empty:
                return None

            # Filter for sovereign bond yield curve
            sovereign = df[df["曲线名称"] == "中债国债收益率曲线"]
            if sovereign.empty:
                return None

            # Take the most recent row's 10-year column
            latest = sovereign.iloc[-1]
            if "10年" not in latest.index:
                return None

            val = latest["10年"]
            # AKShare returns percentage points (e.g. 1.8172 means 1.8172%)
            return float(val) / 100.0

        return await _run_sync(_fetch)

    async def _fetch_china_lpr_1y(self) -> float | None:
        """Fetch latest 1-year LPR (Loan Prime Rate) from AKShare.

        Uses macro_china_lpr which returns historical LPR data from East Money.

        Returns:
            1-year LPR as decimal (e.g. 0.030 for 3.0%), or None on failure
        """

        def _fetch() -> float | None:
            import akshare as ak  # type: ignore[import-untyped]

            df = ak.macro_china_lpr()
            if df is None or df.empty:
                return None

            latest = df.iloc[-1]
            if "LPR1Y" not in latest.index:
                return None

            val = latest["LPR1Y"]
            # AKShare returns percentage points (e.g. 3.0 means 3.0%)
            return float(val) / 100.0

        return await _run_sync(_fetch)

    async def get_hk_rates(self, rate_date: date | None = None) -> dict[str, float]:
        """Get Hong Kong interest rates.

        Currently uses static rates. To be replaced with HKMA API when available.

        Args:
            rate_date: Date for rates (uses latest if None)

        Returns:
            Dictionary with:
                - ten_year_treasury: 10-year government bond yield
                - three_year_deposit: 3-year deposit rate
                - one_year_deposit: 1-year deposit rate
                - benchmark_rate: HKMA base rate

        Raises:
            ExternalAPIError: If rate fetching fails
        """
        logger.info("Using static Hong Kong rates (HKMA API integration pending)")
        return dict(_STATIC_HK_RATES)

    async def get_rates(
        self,
        market: str = "A_SHARE",
        rate_date: date | None = None,
    ) -> dict[str, float]:
        """Get interest rates for specified market.

        Args:
            market: Market type ('A_SHARE' or 'HK_SHARE')
            rate_date: Date for rates (uses latest if None)

        Returns:
            Dictionary with rate values

        Raises:
            ExternalAPIError: If rate fetching fails
        """
        if market == "HK_SHARE":
            return await self.get_hk_rates(rate_date)
        else:
            return await self.get_china_rates(rate_date)

    async def get_10y_treasury_yield(self) -> float:
        """Get 10-year treasury bond yield (China).

        Returns:
            10-year treasury yield as decimal (e.g., 0.025 for 2.5%)

        Raises:
            ExternalAPIError: If rate fetching fails
        """
        rates = await self.get_china_rates()
        return rates["ten_year_treasury"]

    async def get_3y_deposit_rate(self) -> float:
        """Get 3-year large deposit rate (China).

        Returns:
            3-year deposit rate as decimal (e.g., 0.025 for 2.5%)

        Raises:
            ExternalAPIError: If rate fetching fails
        """
        rates = await self.get_china_rates()
        return rates["three_year_deposit"]

    async def fetch_historical_rates(
        self,
        start_date: date,
        end_date: date,
        market: str = "A_SHARE",
    ) -> list[dict[str, Any]]:
        """Fetch historical interest rates for a date range.

        Args:
            start_date: Start date
            end_date: End date
            market: Market type

        Returns:
            List of rate dictionaries with date and values

        Raises:
            ExternalAPIError: If rate fetching fails
        """
        # Placeholder implementation
        # In production, fetch from time-series API
        logger.warning("Historical rates not implemented, returning single latest rate")

        rates = await self.get_rates(market=market)
        return [
            {
                "rate_date": end_date,
                **rates,
                "rate_source": "PBOC" if market == "A_SHARE" else "HKMA",
            }
        ]
