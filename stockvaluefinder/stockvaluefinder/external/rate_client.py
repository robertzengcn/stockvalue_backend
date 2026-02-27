"""Interest rate fetcher for risk-free rates (treasury yields, deposit rates)."""

import logging
from datetime import date
from typing import Any

import httpx

from stockvaluefinder.utils.errors import ExternalAPIError

logger = logging.getLogger(__name__)


class RateClient:
    """Client for fetching market interest rate data.

    Sources:
    - China: PBOC (People's Bank of China)
    - Hong Kong: HKMA (Hong Kong Monetary Authority)
    - Fallback: Static rates or cached values
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

        Args:
            rate_date: Date for rates (uses latest if None)

        Returns:
            Dictionary with:
                - ten_year_treasury: 10-year government bond yield
                - three_year_deposit: 3-year large deposit rate
                - one_year_deposit: 1-year deposit rate
                - benchmark_rate: PBOC benchmark rate

        Raises:
            ExternalAPIError: If rate fetching fails
        """
        # For now, return static rates as placeholder
        # In production, this would fetch from PBOC or financial data APIs
        logger.warning("Using static China rates (replace with real API in production)")

        return {
            "ten_year_treasury": 0.0235,  # 2.35%
            "three_year_deposit": 0.0215,  # 2.15%
            "one_year_deposit": 0.0175,  # 1.75%
            "benchmark_rate": 0.035,  # 3.5% (1-year LPR)
        }

    async def get_hk_rates(self, rate_date: date | None = None) -> dict[str, float]:
        """Get Hong Kong interest rates.

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
        # For now, return static rates as placeholder
        # In production, this would fetch from HKMA or financial data APIs
        logger.warning(
            "Using static Hong Kong rates (replace with real API in production)"
        )

        return {
            "ten_year_treasury": 0.0415,  # 4.15%
            "three_year_deposit": 0.0400,  # 4.0%
            "one_year_deposit": 0.0450,  # 4.5%
            "benchmark_rate": 0.050,  # 5.0% (HKMA base rate)
        }

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
