"""External data service with multi-source fallback logic (AKShare -> efinance -> Tushare).

Priority order:
1. AKShare (free, open-source, no API key)
2. efinance (free, official East Money library, no API key)
3. Tushare (optional, requires token)
4. Mock data (development mode only)

For **spot price**, efinance ``get_latest_quote`` is preferred first: East Money's
kline API (used by AKShare ``stock_zh_a_hist`` / efinance ``get_quote_history``)
often fails with connection resets, while the realtime quote endpoint is separate.
"""

import logging
import os
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from stockvaluefinder.external.akshare_client import AKShareClient
from stockvaluefinder.external.efinance_client import EFinanceClient
from stockvaluefinder.external.tushare_client import TushareClient
from stockvaluefinder.utils.errors import ExternalAPIError, DataValidationError

logger = logging.getLogger(__name__)


def _is_development_mode() -> bool:
    """Check if development mode is enabled.

    This function checks the environment variable each time it's called,
    rather than caching it at module import time.
    """
    return os.getenv("DEVELOPMENT_MODE", "false").lower() == "true"


class ExternalDataService:
    """Unified data service with automatic fallback to backup sources.

    Priority: AKShare -> efinance -> Tushare -> Mock data (dev mode)
    All sources are free except Tushare which requires a token.
    """

    def __init__(
        self,
        tushare_token: str = "",
        enable_akshare: bool = True,
        enable_efinance: bool = True,
    ) -> None:
        """Initialize external data service.

        Args:
            tushare_token: Tushare Pro API token (optional)
            enable_akshare: Whether to enable AKShare as primary source
            enable_efinance: Whether to enable efinance as secondary source
        """
        self.tushare_token = tushare_token
        self.enable_akshare = enable_akshare
        self.enable_efinance = enable_efinance
        self._tushare: TushareClient | None = None
        self._akshare: AKShareClient | None = None
        self._efinance: EFinanceClient | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize data clients in priority order."""
        # Initialize AKShare (primary - free, open-source)
        if self.enable_akshare:
            self._akshare = AKShareClient()
            available = await self._akshare.check_available()
            if available:
                logger.info("✓ AKShare client initialized as primary data source")
            else:
                logger.warning("✗ AKShare not available")
                self._akshare = None

        # Initialize efinance (secondary - free, official East Money)
        if self.enable_efinance:
            self._efinance = EFinanceClient()
            available = await self._efinance.check_available()
            if available:
                logger.info("✓ efinance client initialized as secondary data source")
            else:
                logger.warning("✗ efinance not available (optional)")
                self._efinance = None

        # Initialize Tushare only if token is provided (optional, legacy)
        if self.tushare_token:
            self._tushare = TushareClient(token=self.tushare_token)
            await self._tushare.__aenter__()
            logger.info("✓ Tushare client initialized as tertiary data source")
        else:
            self._tushare = None
            logger.info("⊘ Tushare token not provided (using free sources only)")

        # Log summary
        sources = []
        if self._akshare:
            sources.append("AKShare")
        if self._efinance:
            sources.append("efinance")
        if self._tushare:
            sources.append("Tushare")
        if _is_development_mode():
            sources.append("Mock(dev)")

        logger.info(f"Data sources initialized: {' -> '.join(sources)}")

        # Mark as initialized
        self._initialized = True

    async def shutdown(self) -> None:
        """Shutdown data clients."""
        if self._tushare:
            await self._tushare.__aexit__(None, None, None)
        # AKShare and efinance don't need cleanup (synchronous libraries)

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
        if not self._initialized:
            raise ExternalAPIError(
                "Data service not initialized. Call initialize() first."
            )

        # Try AKShare first
        if self._akshare and ts_code:
            try:
                logger.debug(f"Fetching stock basic from AKShare: {ts_code}")
                symbol = ts_code.split(".")[0] if "." in ts_code else ts_code
                return await self._akshare.get_stock_info_a(symbol=symbol)
            except ExternalAPIError as e:
                logger.warning(f"AKShare failed for stock_basic: {e}")

        # Fallback to Tushare
        if self._tushare:
            try:
                logger.debug(f"Falling back to Tushare for stock basic: {ts_code}")
                return await self._tushare.get_stock_basic(
                    ts_code=ts_code, list_status=list_status
                )
            except ExternalAPIError as e:
                logger.warning(f"Tushare failed for stock_basic: {e}")

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
        if not self._initialized:
            raise ExternalAPIError(
                "Data service not initialized. Call initialize() first."
            )

        # Try AKShare first
        if self._akshare:
            try:
                logger.debug(f"Fetching daily data from AKShare: {ts_code}")
                symbol = ts_code.split(".")[0] if "." in ts_code else ts_code
                return await self._akshare.get_stock_daily(symbol, start_date, end_date)
            except ExternalAPIError as e:
                logger.warning(f"AKShare failed for daily: {e}")

        # Fallback to Tushare
        if self._tushare:
            try:
                logger.debug(f"Falling back to Tushare for daily: {ts_code}")
                return await self._tushare.get_daily(ts_code, start_date, end_date)
            except ExternalAPIError as e:
                logger.warning(f"Tushare failed for daily: {e}")

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
        if not self._initialized:
            raise ExternalAPIError(
                "Data service not initialized. Call initialize() first."
            )

        result: dict[str, Any] = {}

        # Try Tushare (only source with full financial statement APIs)
        if self._tushare:
            try:
                logger.debug(f"Fetching financials from Tushare: {ts_code} {period}")
                result["income"] = await self._tushare.get_income(
                    ts_code, period, report_type
                )
                result["balance"] = await self._tushare.get_balancesheet(
                    ts_code, period
                )
                result["cashflow"] = await self._tushare.get_cashflow(ts_code, period)
                return result
            except ExternalAPIError as e:
                logger.warning(f"Tushare failed for financials: {e}")

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
        if not self._initialized:
            raise ExternalAPIError(
                "Data service not initialized. Call initialize() first."
            )

        # Try AKShare first
        if self._akshare:
            try:
                logger.debug(f"Fetching dividend data from AKShare: {ts_code}")
                symbol = ts_code.split(".")[0] if "." in ts_code else ts_code
                from datetime import datetime

                current_year = datetime.now().year
                return await self._akshare.get_dividend_by_year(symbol, current_year)
            except ExternalAPIError as e:
                logger.warning(f"AKShare failed for dividend: {e}")

        # Fallback to Tushare
        if self._tushare:
            try:
                logger.debug(f"Falling back to Tushare for dividend: {ts_code}")
                return await self._tushare.get_dividend(ts_code)
            except ExternalAPIError as e:
                logger.warning(f"Tushare failed for dividend: {e}")

        raise ExternalAPIError(f"All data sources failed for dividend: {ts_code}")

    async def get_current_price(self, ts_code: str) -> Decimal:
        """Get current stock price.

        Args:
            ts_code: Stock code (e.g., '600519.SH')

        Returns:
            Current price as Decimal

        Raises:
            ExternalAPIError: If all data sources fail
            DataValidationError: If price data not found
        """
        if not self._initialized:
            raise ExternalAPIError(
                "Data service not initialized. Call initialize() first."
            )

        # Prefer efinance latest quote (avoids flaky East Money kline used by AKShare daily)
        if self._efinance:
            try:
                logger.debug(
                    f"Fetching current price from efinance (latest quote): {ts_code}"
                )
                # get_latest_trade_price uses ef.stock.get_latest_quote which
                # accepts stock codes; get_realtime_quotes only accepts market
                # names like '沪深A股' and rejects raw codes like '600519'.
                price = await self._efinance.get_latest_trade_price(ts_code)
                if price <= 0:
                    raise DataValidationError(
                        f"Invalid efinance price for {ts_code}: {price}"
                    )
                logger.info(f"Current price for {ts_code} (efinance): {price}")
                return Decimal(str(price))
            except (ExternalAPIError, DataValidationError) as e:
                logger.warning(f"efinance failed for current price: {e}")

        # AKShare daily kline (same upstream as efinance history; may fail if kline is blocked)
        if self._akshare:
            try:
                logger.debug(f"Fetching current price from AKShare: {ts_code}")
                symbol = ts_code.split(".")[0] if "." in ts_code else ts_code

                end_date = date.today()
                start_date = end_date - timedelta(days=7)

                daily_data = await self._akshare.get_stock_daily(
                    symbol, start_date, end_date
                )

                if not daily_data:
                    raise DataValidationError(f"No price data found for {ts_code}")

                latest = daily_data[0]
                close_price = float(latest.get("收盘", latest.get("close", 0)))

                if close_price <= 0:
                    raise DataValidationError(
                        f"Invalid price data for {ts_code}: {close_price}"
                    )

                logger.info(f"Current price for {ts_code} (AKShare): {close_price}")
                return Decimal(str(close_price))

            except (ExternalAPIError, DataValidationError) as e:
                logger.warning(f"AKShare failed for current price: {e}")

        # Fallback to Tushare (if available)
        if self._tushare:
            try:
                logger.debug(f"Falling back to Tushare for current price: {ts_code}")
                end_date = date.today()
                start_date = end_date - timedelta(days=7)

                daily_data = await self._tushare.get_daily(
                    ts_code, start_date, end_date
                )

                if not daily_data:
                    raise DataValidationError(f"No price data found for {ts_code}")

                latest = daily_data[0]
                close_price = float(latest.get("close", 0))

                if close_price <= 0:
                    raise DataValidationError(
                        f"Invalid price data for {ts_code}: {close_price}"
                    )

                logger.info(f"Current price for {ts_code} (Tushare): {close_price}")
                return Decimal(str(close_price))

            except (ExternalAPIError, DataValidationError) as e:
                logger.warning(f"Tushare failed for current price: {e}")

        # Fall back to mock data in development mode
        if _is_development_mode():
            logger.warning(f"Using mock current price for development: {ts_code}")
            return self._get_mock_current_price(ts_code)

        raise ExternalAPIError(f"All data sources failed for current price: {ts_code}")

    async def get_shares_outstanding(self, ts_code: str) -> float:
        """Get shares outstanding (in millions).

        Args:
            ts_code: Stock code

        Returns:
            Shares outstanding in millions

        Raises:
            ExternalAPIError: If all data sources fail
        """
        # Primary: AKShare stock_individual_info_em (reliable, free, no period needed)
        if self._akshare:
            try:
                logger.debug(f"Fetching shares outstanding from AKShare: {ts_code}")
                symbol = ts_code.split(".")[0] if "." in ts_code else ts_code
                total_shares = await self._akshare.get_shares_outstanding(symbol)
                shares_millions = total_shares / 1_000_000
                logger.info(
                    f"Shares outstanding for {ts_code} (AKShare): {shares_millions:.2f}M"
                )
                return shares_millions

            except (ExternalAPIError, DataValidationError) as e:
                logger.warning(f"AKShare failed for shares outstanding: {e}")

        # Fallback: AKShare balance sheet (SHARE_CAPITAL column)
        if self._akshare:
            try:
                logger.debug(f"Trying AKShare balance sheet for shares: {ts_code}")
                end_date = date.today()
                period = f"{end_date.year - 1}1231"
                balance_data = await self._akshare.get_balance_sheet(ts_code, period)

                if not balance_data:
                    raise DataValidationError(
                        f"No balance sheet data found for {ts_code}"
                    )

                latest = balance_data[0]
                # East Money balance sheet uses English column names
                total_shares = 0
                for field in ["SHARE_CAPITAL", "总股本", "total_share"]:
                    if field in latest and latest[field]:
                        total_shares = float(latest[field])
                        break

                if total_shares <= 0:
                    raise DataValidationError(
                        f"No shares column in balance sheet for {ts_code}"
                    )

                shares_millions = total_shares / 1_000_000
                logger.info(
                    f"Shares outstanding for {ts_code} (AKShare BS): {shares_millions:.2f}M"
                )
                return shares_millions

            except (ExternalAPIError, DataValidationError) as e:
                logger.warning(f"AKShare balance sheet failed for shares: {e}")

        # Fallback to Tushare (if available)
        if self._tushare:
            try:
                logger.debug(
                    f"Falling back to Tushare for shares outstanding: {ts_code}"
                )

                period = f"{date.today().year - 1}1231"
                balance_data = await self._tushare.get_balancesheet(ts_code, period)

                if not balance_data:
                    raise DataValidationError(
                        f"No balance sheet data found for {ts_code}"
                    )

                latest = balance_data[0]
                total_shares = float(latest.get("total_share", 0))

                if total_shares <= 0:
                    raise DataValidationError(
                        f"Invalid shares data for {ts_code}: {total_shares}"
                    )

                shares_millions = total_shares / 1_000_000
                logger.info(
                    f"Shares outstanding for {ts_code} (Tushare): {shares_millions:.2f}M"
                )
                return shares_millions

            except (ExternalAPIError, DataValidationError) as e:
                logger.warning(f"Tushare fallback failed for shares outstanding: {e}")

        # Fall back to mock data in development mode
        if _is_development_mode():
            logger.warning(f"Using mock shares outstanding for development: {ts_code}")
            return self._get_mock_shares_outstanding(ts_code)

        raise ExternalAPIError(
            f"All data sources failed for shares outstanding: {ts_code}"
        )

    async def get_free_cash_flow(
        self, ts_code: str, period: str | None = None
    ) -> float:
        """Get free cash flow (in millions).

        FCF = Operating Cash Flow - Capital Expenditure

        Args:
            ts_code: Stock code
            period: Reporting period (e.g., '20231231'), defaults to most recent

        Returns:
            Free cash flow in millions

        Raises:
            ExternalAPIError: If data source fails
            DataValidationError: If data not found or incomplete
        """
        # Determine period to use
        if period is None:
            end_date = date.today()
            # Use previous year's full year report
            year = end_date.year - 1
            period = f"{year}1231"

        # Try AKShare first (free, no permission issues)
        if self._akshare:
            try:
                logger.debug(f"Fetching FCF from AKShare: {ts_code} {period}")

                cashflow_data = await self._akshare.get_cash_flow_sheet(ts_code, period)

                if not cashflow_data:
                    raise DataValidationError(
                        f"No cash flow data found for {ts_code} {period}"
                    )

                latest = cashflow_data[0]

                # Log if returned data differs from requested period
                actual_report_date = str(latest.get("REPORT_DATE", ""))
                if actual_report_date and period:
                    actual_clean = actual_report_date.replace("-", "")[:8]
                    if actual_clean != period:
                        logger.info(
                            f"Using available data for {ts_code} from {actual_report_date} "
                            f"(requested {period})"
                        )

                # Get operating cash flow and capital expenditure
                # AKShare stock_cash_flow_sheet_by_report_em uses English field names
                ocf = 0.0
                capex = 0.0

                # Try different field names for operating cash flow
                for field in [
                    "NETCASH_OPERATE",
                    "经营活动产生的现金流量净额",
                    "经营现金流",
                    "ocf",
                    "operating_cash_flow",
                ]:
                    if field in latest and latest[field]:
                        ocf = float(latest[field])
                        break

                # Try different field names for capital expenditure
                for field in [
                    "CONSTRUCT_LONG_ASSET",
                    "购建固定资产、无形资产和其他长期资产支付的现金",
                    "资本支出",
                    "capex",
                    "capital_expenditure",
                ]:
                    if field in latest and latest[field]:
                        capex = float(latest[field])
                        break

                # FCF = OCF - CapEx
                fcf = ocf - abs(capex)

                # Convert to millions (AKShare data is typically in yuan)
                fcf_millions = fcf / 1_000_000

                logger.info(
                    f"FCF for {ts_code} {period} (AKShare): {fcf_millions:.2f}M"
                )
                return fcf_millions

            except (ExternalAPIError, DataValidationError) as e:
                logger.warning(f"AKShare failed for FCF: {e}")

        # Fallback to Tushare (if available)
        if self._tushare:
            try:
                logger.debug(f"Falling back to Tushare for FCF: {ts_code} {period}")

                cashflow_data = await self._tushare.get_cashflow(ts_code, period)

                if not cashflow_data:
                    raise DataValidationError(
                        f"No cash flow data found for {ts_code} {period}"
                    )

                latest = cashflow_data[0]

                ocf = float(latest.get("n_cashflow_act", 0))
                capex = float(latest.get("n_cash_inv_act", 0))

                # FCF = OCF - CapEx (CapEx is usually negative in cash flow statement)
                fcf = ocf + capex

                fcf_millions = fcf / 1_000_000

                logger.info(
                    f"FCF for {ts_code} {period} (Tushare): {fcf_millions:.2f}M"
                )
                return fcf_millions

            except (ExternalAPIError, DataValidationError) as e:
                logger.warning(f"Tushare fallback failed for FCF: {e}")

        # Fall back to mock data in development mode
        if _is_development_mode():
            logger.warning(f"Using mock FCF for development: {ts_code}")
            return self._get_mock_free_cash_flow(ts_code)

        raise ExternalAPIError(f"All data sources failed for FCF: {ts_code}")

    async def get_dividend_yield(self, ts_code: str) -> float:
        """Get gross dividend yield (as decimal, e.g., 0.05 = 5%).

        Args:
            ts_code: Stock code

        Returns:
            Gross dividend yield as decimal

        Raises:
            ExternalAPIError: If all data sources fail
            DataValidationError: If dividend data not found
        """
        if not self._initialized:
            raise ExternalAPIError(
                "Data service not initialized. Call initialize() first."
            )

        # Try AKShare first (free, no permission issues)
        if self._akshare:
            try:
                logger.debug(f"Fetching dividend yield from AKShare: {ts_code}")

                # Get current price
                current_price = await self.get_current_price(ts_code)

                # Get dividend history (Sina detail) and approximate TTM dividend.
                symbol = ts_code.split(".")[0] if "." in ts_code else ts_code
                history = await self._akshare.get_dividend_history(symbol)
                if not history:
                    raise DataValidationError(f"No dividend data found for {ts_code}")

                # Use latest up to 4 records as a proxy for TTM.
                # Sina detail is usually "per 10 shares" (派息); convert to per share by /10.
                total_dividend_per10 = 0.0
                for record in history[:4]:
                    total_dividend_per10 += float(record.get("派息", 0) or 0)
                dividend_per_share = total_dividend_per10 / 10.0

                # Calculate yield
                dividend_yield = dividend_per_share / float(current_price)

                logger.info(
                    f"Dividend yield for {ts_code} (AKShare): {dividend_yield:.4f}"
                )
                return dividend_yield

            except (ExternalAPIError, DataValidationError) as e:
                logger.warning(f"AKShare failed for dividend yield: {e}")

        # Fallback to Tushare (if available)
        if self._tushare:
            try:
                logger.debug(f"Falling back to Tushare for dividend yield: {ts_code}")

                # Get current price first
                current_price = await self.get_current_price(ts_code)

                # Get dividend data
                dividend_data = await self._tushare.get_dividend(ts_code)

                if not dividend_data:
                    raise DataValidationError(f"No dividend data found for {ts_code}")

                # Calculate TTM (trailing twelve months) dividend
                # Sum dividends from the last 4 quarters or most recent year
                total_dividend = 0.0
                for record in dividend_data[:4]:  # Last 4 dividend records
                    div_amount = (
                        float(record.get("div_operate", 0)) / 10
                    )  # Per 10 shares
                    total_dividend += div_amount

                # Dividend per share
                dividend_per_share = total_dividend / 10  # Convert to per share

                # Calculate yield
                if current_price <= 0:
                    raise DataValidationError(
                        f"Invalid price for yield calculation: {current_price}"
                    )

                dividend_yield = dividend_per_share / float(current_price)

                logger.info(
                    f"Dividend yield for {ts_code} (Tushare): {dividend_yield:.4f} ({dividend_yield * 100:.2f}%)"
                )
                return dividend_yield

            except (ExternalAPIError, DataValidationError) as e:
                logger.warning(f"Tushare fallback failed for dividend yield: {e}")

        # Fall back to mock data in development mode
        if _is_development_mode():
            logger.warning(f"Using mock dividend yield for development: {ts_code}")
            return self._get_mock_dividend_yield(ts_code)

        raise ExternalAPIError(f"All data sources failed for dividend yield: {ts_code}")

    async def get_financial_report(
        self, ts_code: str, year: int | None = None
    ) -> dict[str, Any]:
        """Get complete financial report data for risk analysis.

        Args:
            ts_code: Stock code
            year: Fiscal year (defaults to previous year)

        Returns:
            Dictionary with financial report data

        Raises:
            ExternalAPIError: If data source fails
            DataValidationError: If data not found
        """
        if not self._initialized:
            raise ExternalAPIError(
                "Data service not initialized. Call initialize() first."
            )

        # Determine period
        if year is None:
            year = date.today().year - 1

        period = f"{year}1231"
        symbol = ts_code.split(".")[0] if "." in ts_code else ts_code

        # Try AKShare first (free, open-source)
        if self._akshare:
            try:
                logger.debug(
                    f"Fetching financial report from AKShare: {ts_code} {year}"
                )
                return await self._get_financial_report_from_akshare(
                    ts_code, year, period
                )
            except (ExternalAPIError, DataValidationError) as e:
                logger.warning(f"AKShare failed for financial report: {e}")

        # Try efinance second (free, official East Money)
        if self._efinance:
            try:
                logger.debug(
                    f"Fetching financial report from efinance: {ts_code} {year}"
                )
                return await self._get_financial_report_from_efinance(
                    symbol, year, period
                )
            except (ExternalAPIError, DataValidationError) as e:
                logger.warning(f"efinance failed for financial report: {e}")

        # Try Tushare third (if token available)
        if self._tushare:
            try:
                logger.debug(
                    f"Fetching financial report from Tushare: {ts_code} {year}"
                )
                return await self._get_financial_report_from_tushare(
                    ts_code, year, period
                )
            except (ExternalAPIError, DataValidationError) as e:
                logger.warning(f"Tushare failed for financial report: {e}")

        # Fall back to mock data in development mode
        if _is_development_mode():
            logger.warning(
                f"Using mock financial data for development: {ts_code} {year}"
            )
            return self._get_mock_financial_report(ts_code, year)

        # All sources failed
        raise ExternalAPIError(
            f"All data sources failed for {ts_code} {year}. "
            f"Enable DEVELOPMENT_MODE=true for mock data or add TUSHARE_TOKEN."
        )

    async def _get_financial_report_from_akshare(
        self,
        ts_code: str,
        year: int,
        period: str,
    ) -> dict[str, Any]:
        """Get financial report from AKShare.

        Args:
            ts_code: Stock code (e.g. ``600519.SH``)
            year: Fiscal year
            period: Period string

        Returns:
            Financial report dictionary
        """
        # Get all three statements
        if self._akshare is None:
            raise ExternalAPIError("AKShare client is not initialized")
        income_data = await self._akshare.get_profit_sheet(ts_code, period)
        balance_data = await self._akshare.get_balance_sheet(ts_code, period)
        cashflow_data = await self._akshare.get_cash_flow_sheet(ts_code, period)

        if not income_data or not balance_data or not cashflow_data:
            raise DataValidationError(
                f"Incomplete financial data from AKShare: {ts_code} {period}"
            )

        # Extract data (AKShare stock_*_by_report_em uses English field names)
        income = income_data[0]
        balance = balance_data[0]
        cashflow = cashflow_data[0]

        # Derive actual fiscal year from REPORT_DATE in case of period fallback
        actual_year = year
        report_date_str = str(income.get("REPORT_DATE", ""))
        if report_date_str and report_date_str not in ("0", "nan", "None"):
            try:
                actual_year = int(report_date_str[:4])
            except (ValueError, IndexError):
                pass

        # Map English field names from AKShare stock_*_by_report_em APIs
        report = {
            "ticker": ts_code,
            "report_id": uuid4(),
            "period": f"{actual_year}-12-31",
            "report_type": "ANNUAL",
            "fiscal_year": actual_year,
            "fiscal_quarter": None,
            # Income statement
            "revenue": str(
                income.get(
                    "TOTAL_OPERATE_INCOME",
                    income.get("营业总收入", income.get("营业收入", 0)),
                )
            ),
            "net_income": str(
                income.get(
                    "NETPROFIT",
                    income.get("净利润", income.get("归属母公司所有者的净利润", 0)),
                )
            ),
            "operating_cash_flow": str(
                cashflow.get(
                    "NETCASH_OPERATE", cashflow.get("经营活动产生的现金流量净额", 0)
                )
            ),
            "gross_margin": self._calculate_gross_margin_from_akshare(income),
            # Balance sheet
            "assets_total": str(
                balance.get("TOTAL_ASSETS", balance.get("资产总计", 0))
            ),
            "liabilities_total": str(
                balance.get("TOTAL_LIABILITIES", balance.get("负债合计", 0))
            ),
            "equity_total": str(
                balance.get("TOTAL_EQUITY", balance.get("所有者权益合计", 0))
            ),
            "accounts_receivable": str(
                balance.get("ACCOUNTS_RECE", balance.get("应收账款", 0))
            ),
            "inventory": str(balance.get("INVENTORY", balance.get("存货", 0))),
            "fixed_assets": str(balance.get("FIXED_ASSET", balance.get("固定资产", 0))),
            "goodwill": str(balance.get("GOODWILL", balance.get("商誉", 0))),
            "cash_and_equivalents": str(
                balance.get("MONETARYFUNDS", balance.get("货币资金", 0))
            ),
            "interest_bearing_debt": str(
                balance.get("TOTAL_LIABILITIES", balance.get("负债合计", 0))
            ),
            # M-Score raw financial fields
            "cost_of_goods": str(income.get("OPERATE_COST", income.get("营业成本", 0))),
            "sga_expense": str(
                income.get("TOTAL_OPERATE_COST", income.get("营业总成本", 0))
            ),
            "total_current_assets": str(
                balance.get("TOTAL_CURRENT_ASSETS", balance.get("流动资产合计", 0))
            ),
            "ppe": str(balance.get("FIXED_ASSET", balance.get("固定资产", 0))),
            "long_term_debt": str(balance.get("LONG_LOAN", balance.get("长期借款", 0))),
            "total_liabilities": str(
                balance.get("TOTAL_LIABILITIES", balance.get("负债合计", 0))
            ),
            "report_source": "AKShare",
        }

        if actual_year != year:
            logger.info(
                f"Using available data for {ts_code} from {actual_year} "
                f"(requested {year})"
            )
        logger.info(
            f"Financial report fetched from AKShare for {ts_code} {actual_year}"
        )
        return report

    async def _get_financial_report_from_efinance(
        self,
        symbol: str,
        year: int,
        period: str,
    ) -> dict[str, Any]:
        """Get financial report from efinance.

        Args:
            symbol: Stock symbol
            year: Fiscal year
            period: Period string

        Returns:
            Financial report dictionary
        """
        # Get all three statements
        if self._efinance is None:
            raise ExternalAPIError("EFinance client is not initialized")
        income_data = await self._efinance.get_profit_sheet(symbol, period)
        balance_data = await self._efinance.get_balance_sheet(symbol, period)
        cashflow_data = await self._efinance.get_cash_flow_sheet(symbol, period)

        if not income_data or not balance_data or not cashflow_data:
            raise DataValidationError(
                f"Incomplete financial data from efinance: {symbol} {period}"
            )

        # Extract data
        income = income_data[0]
        balance = balance_data[0]
        cashflow = cashflow_data[0]

        report = {
            "ticker": f"{symbol}.SH",
            "report_id": uuid4(),
            "period": f"{year}-12-31",
            "report_type": "ANNUAL",
            "fiscal_year": year,
            "fiscal_quarter": None,
            # Income statement (efinance uses similar field names to Tushare)
            "revenue": str(income.get("营业总收入", income.get("营业收入", 0))),
            "net_income": str(
                income.get("净利润", income.get("归属母公司所有者的净利润", 0))
            ),
            "operating_cash_flow": str(cashflow.get("经营活动产生的现金流量净额", 0)),
            "gross_margin": self._calculate_gross_margin_from_efinance(income),
            # Balance sheet
            "assets_total": str(balance.get("资产总计", 0)),
            "liabilities_total": str(balance.get("负债合计", 0)),
            "equity_total": str(balance.get("所有者权益合计", 0)),
            "accounts_receivable": str(balance.get("应收账款", 0)),
            "inventory": str(balance.get("存货", 0)),
            "fixed_assets": str(balance.get("固定资产", 0)),
            "goodwill": str(balance.get("商誉", 0)),
            "cash_and_equivalents": str(balance.get("货币资金", 0)),
            "interest_bearing_debt": str(balance.get("负债合计", 0)),
            # M-Score raw financial fields
            "cost_of_goods": str(income.get("营业成本", income.get("OPERATE_COST", 0))),
            "sga_expense": str(
                income.get("营业总成本", income.get("TOTAL_OPERATE_COST", 0))
            ),
            "total_current_assets": str(
                balance.get("流动资产合计", balance.get("TOTAL_CURRENT_ASSETS", 0))
            ),
            "ppe": str(balance.get("固定资产", balance.get("FIXED_ASSET", 0))),
            "long_term_debt": str(balance.get("长期借款", balance.get("LONG_LOAN", 0))),
            "total_liabilities": str(
                balance.get("负债合计", balance.get("TOTAL_LIABILITIES", 0))
            ),
            "report_source": "efinance",
        }

        logger.info(f"Financial report fetched from efinance for {symbol} {period}")
        return report

    async def _get_financial_report_from_tushare(
        self,
        ts_code: str,
        year: int,
        period: str,
    ) -> dict[str, Any]:
        """Get financial report from Tushare.

        Args:
            ts_code: Stock code with market suffix
            year: Fiscal year
            period: Period string

        Returns:
            Financial report dictionary
        """
        # Get all three statements
        if self._tushare is None:
            raise ExternalAPIError("Tushare client is not initialized")
        income_data = await self._tushare.get_income(ts_code, period)
        balance_data = await self._tushare.get_balancesheet(ts_code, period)
        cashflow_data = await self._tushare.get_cashflow(ts_code, period)

        if not income_data or not balance_data or not cashflow_data:
            raise DataValidationError(
                f"Incomplete financial data from Tushare: {ts_code} {period}"
            )

        # Extract key metrics
        income = income_data[0]
        balance = balance_data[0]
        cashflow = cashflow_data[0]

        report = {
            "ticker": ts_code,
            "report_id": uuid4(),
            "period": f"{year}-12-31",
            "report_type": "ANNUAL",
            "fiscal_year": year,
            "fiscal_quarter": None,
            # Income statement
            "revenue": str(income.get("revenue", 0)),
            "net_income": str(income.get("n_income", 0)),
            "operating_cash_flow": str(cashflow.get("n_cashflow_act", 0)),
            "gross_margin": self._calculate_gross_margin(income),
            # Balance sheet
            "assets_total": str(balance.get("total_assets", 0)),
            "liabilities_total": str(balance.get("total_hldr_eqy_exc_min_int", 0)),
            "equity_total": str(balance.get("equity", 0)),
            "accounts_receivable": str(balance.get("accounts_receivable", 0)),
            "inventory": str(balance.get("inventories", 0)),
            "fixed_assets": str(balance.get("fix_assets", 0)),
            "goodwill": str(balance.get("goodwill", 0)),
            "cash_and_equivalents": str(balance.get("cash_equivalents", 0)),
            "interest_bearing_debt": str(balance.get("total_liab", 0)),
            # M-Score raw financial fields
            "cost_of_goods": str(
                income.get("operating_cost", income.get("营业成本", 0))
            ),
            "sga_expense": str(
                income.get("total_operating_cost", income.get("营业总成本", 0))
            ),
            "total_current_assets": str(
                balance.get("total_current_assets", balance.get("流动资产合计", 0))
            ),
            "ppe": str(balance.get("fix_assets", balance.get("固定资产", 0))),
            "long_term_debt": str(
                balance.get("long_term_loan", balance.get("长期借款", 0))
            ),
            "total_liabilities": str(
                balance.get("total_liab", balance.get("负债合计", 0))
            ),
            "report_source": "Tushare",
        }

        logger.info(f"Financial report fetched from Tushare for {ts_code} {period}")
        return report

    def _calculate_gross_margin_from_akshare(self, income: dict[str, Any]) -> float:
        """Calculate gross margin from AKShare income statement data.

        Args:
            income: Income statement data from AKShare

        Returns:
            Gross margin as percentage
        """
        revenue = float(
            income.get(
                "TOTAL_OPERATE_INCOME",
                income.get("营业总收入", income.get("营业收入", 0)),
            )
        )
        cost = float(
            income.get(
                "OPERATE_COST", income.get("营业成本", income.get("营业总成本", 0))
            )
        )

        if revenue <= 0:
            return 0.0

        gross_margin = ((revenue - cost) / revenue) * 100
        return round(gross_margin, 2)

    def _calculate_gross_margin_from_efinance(self, income: dict[str, Any]) -> float:
        """Calculate gross margin from efinance income statement data (Chinese field names).

        Args:
            income: Income statement data from efinance

        Returns:
            Gross margin as percentage
        """
        return self._calculate_gross_margin_from_akshare(income)  # Same field names

    def _calculate_gross_margin(self, income: dict[str, Any]) -> float:
        """Calculate gross margin from income statement data.

        Args:
            income: Income statement data

        Returns:
            Gross margin as percentage
        """
        revenue = float(income.get("revenue", 0))
        cost = float(income.get("operating_cost", 0))

        if revenue <= 0:
            return 0.0

        gross_margin = ((revenue - cost) / revenue) * 100
        return round(gross_margin, 2)

    def _get_mock_financial_report(self, ts_code: str, year: int) -> dict[str, Any]:
        """Generate mock financial report data for development.

        Args:
            ts_code: Stock code
            year: Fiscal year

        Returns:
            Mock financial report data
        """
        # Mock data for a healthy company (low risk)
        return {
            "ticker": ts_code,
            "report_id": uuid4(),
            "period": f"{year}-12-31",
            "report_type": "ANNUAL",
            "fiscal_year": year,
            "fiscal_quarter": None,
            # Income statement (in millions CNY)
            "revenue": "50000000000",  # 50 billion
            "net_income": "10000000000",  # 10 billion
            "operating_cash_flow": "12000000000",  # 12 billion
            "gross_margin": 35.5,
            # Balance sheet (in millions CNY)
            "assets_total": "100000000000",  # 100 billion
            "liabilities_total": "30000000000",  # 30 billion
            "equity_total": "70000000000",  # 70 billion
            "accounts_receivable": "5000000000",  # 5 billion
            "inventory": "8000000000",  # 8 billion
            "fixed_assets": "40000000000",  # 40 billion
            "goodwill": "2000000000",  # 2 billion (below 30% threshold)
            "cash_and_equivalents": "15000000000",  # 15 billion
            "interest_bearing_debt": "10000000000",  # 10 billion
            # M-Score raw financial fields
            "cost_of_goods": "35000000000",  # 35 billion
            "sga_expense": "40000000000",  # 40 billion
            "total_current_assets": "45000000000",  # 45 billion
            "ppe": "40000000000",  # 40 billion
            "long_term_debt": "8000000000",  # 8 billion
            "total_liabilities": "30000000000",  # 30 billion
            "report_source": "Mock (Development Mode)",
        }

    def _get_mock_current_price(self, ts_code: str) -> Decimal:
        """Generate mock current price for development.

        Args:
            ts_code: Stock code

        Returns:
            Mock current price
        """
        # Generate a realistic price based on stock code hash
        # This ensures the same stock always gets the same mock price
        hash_val = hash(ts_code) % 1000
        base_price = 10.0 + (hash_val / 10.0)
        return Decimal(str(round(base_price, 2)))

    def _get_mock_shares_outstanding(self, ts_code: str) -> float:
        """Generate mock shares outstanding for development.

        Args:
            ts_code: Stock code

        Returns:
            Mock shares outstanding in millions
        """
        # Generate a realistic number: 500M to 5000M shares
        hash_val = hash(ts_code) % 4500
        shares_millions = 500.0 + hash_val
        return shares_millions

    def _get_mock_free_cash_flow(self, ts_code: str) -> float:
        """Generate mock free cash flow for development.

        Args:
            ts_code: Stock code

        Returns:
            Mock FCF in millions
        """
        # Generate a realistic FCF: 1000M to 10000M
        hash_val = hash(ts_code) % 9000
        fcf_millions = 1000.0 + hash_val
        return fcf_millions

    def _get_mock_dividend_yield(self, ts_code: str) -> float:
        """Generate mock dividend yield for development.

        Args:
            ts_code: Stock code

        Returns:
            Mock dividend yield as decimal (e.g., 0.05 for 5%)
        """
        # Generate a realistic yield: 2% to 6%
        hash_val = hash(ts_code) % 40
        yield_percent = 2.0 + hash_val
        return yield_percent / 100.0
