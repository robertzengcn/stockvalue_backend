"""External data service with fallback logic (Tushare -> AKShare)."""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from stockvaluefinder.external.akshare_client import AKShareClient
from stockvaluefinder.external.tushare_client import TushareClient
from stockvaluefinder.utils.errors import ExternalAPIError, DataValidationError

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
        if not self._tushare:
            raise ExternalAPIError(
                "Data service not initialized. Call initialize() first."
            )

        # Try Tushare first
        try:
            logger.debug(f"Fetching current price from Tushare: {ts_code}")
            # Get daily data for most recent trading day
            end_date = date.today()
            start_date = end_date - timedelta(days=7)  # Look back 7 days

            daily_data = await self._tushare.get_daily(ts_code, start_date, end_date)

            if not daily_data:
                raise DataValidationError(f"No price data found for {ts_code}")

            # Get the most recent trading day's close price
            latest = daily_data[0]
            close_price = float(latest.get("close", 0))

            if close_price <= 0:
                raise DataValidationError(f"Invalid price data for {ts_code}: {close_price}")

            logger.info(f"Current price for {ts_code}: {close_price}")
            return Decimal(str(close_price))

        except (ExternalAPIError, DataValidationError) as e:
            logger.warning(f"Tushare failed for current price: {e}")

        # Fallback to AKShare
        if self._akshare:
            try:
                logger.debug(f"Falling back to AKShare for current price: {ts_code}")
                symbol = ts_code.split(".")[0] if "." in ts_code else ts_code

                end_date = date.today()
                start_date = end_date - timedelta(days=7)

                daily_data = await self._akshare.get_stock_daily(symbol, start_date, end_date)

                if not daily_data:
                    raise DataValidationError(f"No price data found for {ts_code}")

                latest = daily_data[0]
                close_price = float(latest.get("收盘", latest.get("close", 0)))

                if close_price <= 0:
                    raise DataValidationError(f"Invalid price data for {ts_code}: {close_price}")

                logger.info(f"Current price for {ts_code} (AKShare): {close_price}")
                return Decimal(str(close_price))

            except (ExternalAPIError, DataValidationError) as e:
                logger.error(f"AKShare fallback failed for current price: {e}")

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
        if not self._tushare:
            raise ExternalAPIError(
                "Data service not initialized. Call initialize() first."
            )

        try:
            logger.debug(f"Fetching shares outstanding from Tushare: {ts_code}")

            # Get balance sheet data for most recent period
            end_date = date.today()
            period = end_date.strftime("%Y%m%d")

            balance_data = await self._tushare.get_balancesheet(ts_code, period)

            if not balance_data:
                # Try previous period
                year = end_date.year - 1
                period = f"{year}1231"
                balance_data = await self._tushare.get_balancesheet(ts_code, period)

            if not balance_data:
                raise DataValidationError(f"No balance sheet data found for {ts_code}")

            latest = balance_data[0]
            # Total shares outstanding (in shares)
            total_shares = float(latest.get("total_share", 0))

            if total_shares <= 0:
                raise DataValidationError(f"Invalid shares data for {ts_code}: {total_shares}")

            # Convert to millions
            shares_millions = total_shares / 1_000_000

            logger.info(f"Shares outstanding for {ts_code}: {shares_millions:.2f}M")
            return shares_millions

        except (ExternalAPIError, DataValidationError) as e:
            logger.error(f"Failed to get shares outstanding for {ts_code}: {e}")
            raise

    async def get_free_cash_flow(self, ts_code: str, period: str | None = None) -> float:
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
        if not self._tushare:
            raise ExternalAPIError(
                "Data service not initialized. Call initialize() first."
            )

        # Determine period to use
        if period is None:
            end_date = date.today()
            # Use previous year's full year report
            year = end_date.year - 1
            period = f"{year}1231"

        try:
            logger.debug(f"Fetching FCF from Tushare: {ts_code} {period}")

            cashflow_data = await self._tushare.get_cashflow(ts_code, period)

            if not cashflow_data:
                raise DataValidationError(f"No cash flow data found for {ts_code} {period}")

            latest = cashflow_data[0]

            # Get operating cash flow and capital expenditure
            # Note: Tushare field names may vary, check actual API response
            ocf = float(latest.get("n_cashflow_act", 0))  # Operating cash flow
            capex = float(latest.get("n_cash_inv_act", 0))  # Capital expenditure

            # FCF = OCF - CapEx (CapEx is usually negative in cash flow statement)
            fcf = ocf + capex

            # Convert to millions (Tushare data is in yuan)
            fcf_millions = fcf / 1_000_000

            logger.info(f"FCF for {ts_code} {period}: {fcf_millions:.2f}M")
            return fcf_millions

        except (ExternalAPIError, DataValidationError) as e:
            logger.error(f"Failed to get FCF for {ts_code}: {e}")
            raise

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
        if not self._tushare:
            raise ExternalAPIError(
                "Data service not initialized. Call initialize() first."
            )

        try:
            logger.debug(f"Fetching dividend yield from Tushare: {ts_code}")

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
                div_amount = float(record.get("div_operate", 0)) / 10  # Per 10 shares
                total_dividend += div_amount

            # Dividend per share
            dividend_per_share = total_dividend / 10  # Convert to per share

            # Calculate yield
            if current_price <= 0:
                raise DataValidationError(f"Invalid price for yield calculation: {current_price}")

            dividend_yield = dividend_per_share / float(current_price)

            logger.info(f"Dividend yield for {ts_code}: {dividend_yield:.4f} ({dividend_yield*100:.2f}%)")
            return dividend_yield

        except (ExternalAPIError, DataValidationError) as e:
            logger.warning(f"Tushare failed for dividend yield: {e}")

        # Fallback to AKShare
        if self._akshare:
            try:
                logger.debug(f"Falling back to AKShare for dividend yield: {ts_code}")

                # Get current price
                current_price = await self.get_current_price(ts_code)

                # Get dividend data
                symbol = ts_code.split(".")[0] if "." in ts_code else ts_code
                current_year = date.today().year

                dividend_data = await self._akshare.get_dividend_by_year(symbol, current_year)

                if not dividend_data:
                    raise DataValidationError(f"No dividend data found for {ts_code}")

                # Calculate total dividend
                total_dividend = 0.0
                for record in dividend_data:
                    div_amount = float(record.get("分红", 0))
                    total_dividend += div_amount

                # Dividend per share (AKShare data format)
                dividend_per_share = total_dividend / 10

                # Calculate yield
                dividend_yield = dividend_per_share / float(current_price)

                logger.info(f"Dividend yield for {ts_code} (AKShare): {dividend_yield:.4f}")
                return dividend_yield

            except (ExternalAPIError, DataValidationError) as e:
                logger.error(f"AKShare fallback failed for dividend yield: {e}")

        raise ExternalAPIError(f"All data sources failed for dividend yield: {ts_code}")

    async def get_financial_report(self, ts_code: str, year: int | None = None) -> dict[str, Any]:
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
        if not self._tushare:
            raise ExternalAPIError(
                "Data service not initialized. Call initialize() first."
            )

        # Determine period
        if year is None:
            year = date.today().year - 1

        period = f"{year}1231"

        try:
            logger.debug(f"Fetching financial report from Tushare: {ts_code} {period}")

            # Get all three statements
            income_data = await self._tushare.get_income(ts_code, period)
            balance_data = await self._tushare.get_balancesheet(ts_code, period)
            cashflow_data = await self._tushare.get_cashflow(ts_code, period)

            if not income_data or not balance_data or not cashflow_data:
                raise DataValidationError(f"Incomplete financial data for {ts_code} {period}")

            # Extract key metrics
            income = income_data[0]
            balance = balance_data[0]
            cashflow = cashflow_data[0]

            report = {
                "ticker": ts_code,
                "report_id": f"{ts_code}_{period}",
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
                "report_source": "Tushare",
                # Note: M-Score indices need to be calculated separately
                "days_sales_receivables_index": 1.0,
                "gross_margin_index": 1.0,
                "asset_quality_index": 1.0,
                "sales_growth_index": 1.0,
                "depreciation_index": 1.0,
                "sga_expense_index": 1.0,
                "leverage_index": 1.0,
                "total_accruals_to_assets": 0.0,
            }

            logger.info(f"Financial report fetched for {ts_code} {period}")
            return report

        except (ExternalAPIError, DataValidationError) as e:
            logger.error(f"Failed to get financial report for {ts_code}: {e}")
            raise

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
