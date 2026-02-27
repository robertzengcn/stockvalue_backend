"""External data service with fallback logic (Tushare -> AKShare)."""

import logging
from datetime import date
from typing import Any

from stockvaluefinder.external.akshare_client import AKShareClient
from stockvaluefinder.external.tushare_client import TushareClient
from stockvaluefinder.utils.errors import ExternalAPIError

logger = logging.getLogger(__name__)


class ExternalDataService:
    """Unified data service with automatic fallback to backup sources.

    Tries Tushare first, falls back to AKShare on failure.
    """

    def __init__(
        self,
        tushare_token: str,
        enable_akshare: bool = True,
    ) -> None:
        """Initialize external data service.

        Args:
            tushare_token: Tushare Pro API token
            enable_akshare: Whether to enable AKShare as fallback
        """
        self.tushare_token = tushare_token
        self.enable_akshare = enable_akshare
        self._tushare: TushareClient | None = None
        self._akshare: AKShareClient | None = None

    async def initialize(self) -> None:
        """Initialize data clients."""
        self._tushare = TushareClient(token=self.tushare_token)
        await self._tushare.__aenter__()

        if self.enable_akshare:
            self._akshare = AKShareClient()
            available = await self._akshare.check_available()
            if available:
                logger.info("AKShare client initialized as fallback")
            else:
                logger.warning("AKShare not available, fallback disabled")
                self._akshare = None

    async def shutdown(self) -> None:
        """Shutdown data clients."""
        if self._tushare:
            await self._tushare.__aexit__(None, None, None)
        # AKShare doesn't need cleanup

    async def get_stock_basic(
        self,
        ts_code: str | None = None,
        list_status: str = "L",
    ) -> list[dict[str, Any]]:
        """Get stock basic information with fallback.

        Args:
            ts_code: Stock code (e.g., '600519.SH')
            list_status: Listing status

        Returns:
            List of stock basic information

        Raises:
            ExternalAPIError: If all data sources fail
        """
        if not self._tushare:
            raise ExternalAPIError(
                "Data service not initialized. Call initialize() first."
            )

        # Try Tushare first
        try:
            logger.debug(f"Fetching stock basic from Tushare: ts_code={ts_code}")
            return await self._tushare.get_stock_basic(
                ts_code=ts_code, list_status=list_status
            )
        except ExternalAPIError as e:
            logger.warning(f"Tushare failed for stock_basic: {e}")

        # Fallback to AKShare
        if self._akshare and ts_code:
            try:
                logger.debug(f"Falling back to AKShare for stock basic: {ts_code}")
                # Extract symbol from ts_code (e.g., '600519.SH' -> '600519')
                symbol = ts_code.split(".")[0] if "." in ts_code else ts_code
                return await self._akshare.get_stock_info_a(symbol=symbol)
            except ExternalAPIError as e:
                logger.error(f"AKShare fallback failed for stock_basic: {e}")

        raise ExternalAPIError(
            f"All data sources failed for stock_basic: ts_code={ts_code}"
        )

    async def get_daily(
        self,
        ts_code: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Get daily market data with fallback.

        Args:
            ts_code: Stock code
            start_date: Start date
            end_date: End date

        Returns:
            List of daily market data

        Raises:
            ExternalAPIError: If all data sources fail
        """
        if not self._tushare:
            raise ExternalAPIError(
                "Data service not initialized. Call initialize() first."
            )

        # Try Tushare first
        try:
            logger.debug(f"Fetching daily data from Tushare: {ts_code}")
            return await self._tushare.get_daily(ts_code, start_date, end_date)
        except ExternalAPIError as e:
            logger.warning(f"Tushare failed for daily: {e}")

        # Fallback to AKShare
        if self._akshare:
            try:
                logger.debug(f"Falling back to AKShare for daily: {ts_code}")
                symbol = ts_code.split(".")[0] if "." in ts_code else ts_code
                return await self._akshare.get_stock_daily(symbol, start_date, end_date)
            except ExternalAPIError as e:
                logger.error(f"AKShare fallback failed for daily: {e}")

        raise ExternalAPIError(f"All data sources failed for daily: {ts_code}")

    async def get_financials(
        self,
        ts_code: str,
        period: str,
        report_type: str = "annual",
    ) -> dict[str, Any]:
        """Get financial data with fallback.

        Args:
            ts_code: Stock code
            period: Reporting period (e.g., '20231231')
            report_type: Report type

        Returns:
            Dictionary with income, balance, cashflow data

        Raises:
            ExternalAPIError: If all data sources fail
        """
        if not self._tushare:
            raise ExternalAPIError(
                "Data service not initialized. Call initialize() first."
            )

        result: dict[str, Any] = {}

        # Try Tushare first
        try:
            logger.debug(f"Fetching financials from Tushare: {ts_code} {period}")
            result["income"] = await self._tushare.get_income(
                ts_code, period, report_type
            )
            result["balance"] = await self._tushare.get_balancesheet(ts_code, period)
            result["cashflow"] = await self._tushare.get_cashflow(ts_code, period)
            return result
        except ExternalAPIError as e:
            logger.warning(f"Tushare failed for financials: {e}")

        # AKShare doesn't have equivalent financial data APIs in the same format
        raise ExternalAPIError(f"Data source failed for financials: {ts_code} {period}")

    async def get_dividend(
        self,
        ts_code: str,
    ) -> list[dict[str, Any]]:
        """Get dividend data with fallback.

        Args:
            ts_code: Stock code

        Returns:
            List of dividend data

        Raises:
            ExternalAPIError: If all data sources fail
        """
        if not self._tushare:
            raise ExternalAPIError(
                "Data service not initialized. Call initialize() first."
            )

        # Try Tushare first
        try:
            logger.debug(f"Fetching dividend data from Tushare: {ts_code}")
            return await self._tushare.get_dividend(ts_code)
        except ExternalAPIError as e:
            logger.warning(f"Tushare failed for dividend: {e}")

        # Fallback to AKShare
        if self._akshare:
            try:
                logger.debug(f"Falling back to AKShare for dividend: {ts_code}")
                symbol = ts_code.split(".")[0] if "." in ts_code else ts_code
                # Get current year's dividend
                from datetime import datetime

                current_year = datetime.now().year
                return await self._akshare.get_dividend_by_year(symbol, current_year)
            except ExternalAPIError as e:
                logger.error(f"AKShare fallback failed for dividend: {e}")

        raise ExternalAPIError(f"All data sources failed for dividend: {ts_code}")
