"""Shared helpers for ensuring required records exist before analysis persistence."""

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.external.data_service import ExternalDataService
from stockvaluefinder.models.enums import Market, ReportType
from stockvaluefinder.models.financial import FinancialReportCreate
from stockvaluefinder.models.stock import StockCreate
from stockvaluefinder.repositories.financial_repo import FinancialReportRepository
from stockvaluefinder.repositories.stock_repo import StockRepository

logger = logging.getLogger(__name__)


async def ensure_stock_exists(
    ticker: str,
    market: Market,
    data_service: ExternalDataService,
    db: AsyncSession,
) -> None:
    """Ensure a stock record exists in the stocks table.

    Checks if the ticker exists and creates a stock record if missing.
    This satisfies foreign key constraints from analysis tables
    (yield_gaps, valuation_results, risk_scores) that reference stocks.

    Args:
        ticker: Stock ticker (e.g., '600519.SH')
        market: Market enum (A_SHARE or HK_SHARE)
        data_service: External data service for fetching stock info
        db: Database session
    """
    stock_repo = StockRepository(db)
    if await stock_repo.ticker_exists(ticker):
        return

    stock_create = await _fetch_stock_create(ticker, market, data_service)
    if stock_create is not None:
        await stock_repo.create(stock_create)
        logger.info(f"Created stock record for {ticker}")
    else:
        # External API failed — create a minimal record to satisfy FK constraint
        stock_create = StockCreate(
            ticker=ticker,
            name=ticker,
            market=market,
            industry="Unknown",
            list_date=date(2000, 1, 11),
        )
        await stock_repo.create(stock_create)
        logger.warning(
            f"Created minimal stock record for {ticker} (external info unavailable)"
        )


async def _fetch_stock_create(
    ticker: str,
    market: Market,
    data_service: ExternalDataService,
) -> StockCreate | None:
    """Build a StockCreate model by fetching stock info from external data service.

    Handles both AKShare's {item, value} pair format and Tushare's flat dict.

    Args:
        ticker: Stock ticker (e.g., '600519.SH')
        market: Market enum
        data_service: External data service

    Returns:
        StockCreate if info was fetched successfully, None otherwise
    """
    try:
        info_records = await data_service.get_stock_basic(ts_code=ticker)
        if not info_records:
            return None

        # AKShare stock_individual_info_em returns list of {item, value} pairs
        if isinstance(info_records, list) and len(info_records) > 1:
            info_map = {
                r.get("item", ""): r.get("value", "")
                for r in info_records
                if isinstance(r, dict)
            }
            name = str(info_map.get("股票简称", info_map.get("公司名称", ticker)))
            industry = str(info_map.get("行业", info_map.get("所属行业", "Unknown")))
            list_date_str = str(info_map.get("上市时间", ""))
            try:
                list_date = date.fromisoformat(list_date_str.replace("/", "-"))
            except (ValueError, AttributeError):
                list_date = date(2000, 1, 1)
        else:
            # Tushare-style flat dict
            info = info_records[0] if isinstance(info_records, list) else info_records
            name = str(info.get("name", ticker))
            industry = str(info.get("industry", "Unknown"))
            list_date_str = str(info.get("list_date", ""))
            try:
                list_date = date.fromisoformat(list_date_str.replace("/", "-"))
            except (ValueError, AttributeError):
                list_date = date(2000, 1, 1)

        return StockCreate(
            ticker=ticker,
            name=name,
            market=market,
            industry=industry,
            list_date=list_date,
        )
    except Exception as e:
        logger.warning(f"Could not fetch stock info for {ticker}: {e}")
        return None


async def ensure_financial_report_exists(
    report_data: dict[str, Any],
    db: AsyncSession,
) -> UUID:
    """Ensure a financial_reports record exists for the given report_data.

    Creates one from report_data if it doesn't exist, satisfying the risk_scores FK constraint.

    Args:
        report_data: Dict from data_service.get_financial_report()
        db: Database session

    Returns:
        The report_id (UUID) of the persisted or existing financial report
    """
    financial_repo = FinancialReportRepository(db)
    ticker = str(report_data.get("ticker", ""))
    period_str = str(report_data.get("period", ""))
    try:
        period = date.fromisoformat(period_str)
    except (ValueError, AttributeError):
        period = date.today()

    existing = await financial_repo.get_by_ticker_and_period(ticker, period)
    if existing is not None:
        return UUID(str(existing.report_id))
    report_type_str = str(report_data.get("report_type", "ANNUAL")).upper()
    if report_type_str == "QUARTERLY":
        report_type = ReportType.QUARTERLY
        fiscal_quarter = int(report_data.get("fiscal_quarter", 4))
    else:
        report_type = ReportType.ANNUAL
        fiscal_quarter = None

    fr_create = FinancialReportCreate(
        ticker=ticker,
        period=period_str,
        report_type=report_type,
        fiscal_year=int(report_data.get("fiscal_year", period.year)),
        fiscal_quarter=fiscal_quarter,
        revenue=Decimal(str(report_data.get("revenue", "0"))),
        net_income=Decimal(str(report_data.get("net_income", "0"))),
        operating_cash_flow=Decimal(str(report_data.get("operating_cash_flow", "0"))),
        gross_margin=float(report_data.get("gross_margin", 0)),
        assets_total=Decimal(str(report_data.get("assets_total", "0"))),
        liabilities_total=Decimal(str(report_data.get("liabilities_total", "0"))),
        equity_total=Decimal(str(report_data.get("equity_total", "0"))),
        accounts_receivable=Decimal(str(report_data.get("accounts_receivable", "0"))),
        inventory=Decimal(str(report_data.get("inventory", "0"))),
        fixed_assets=Decimal(str(report_data.get("fixed_assets", "0"))),
        goodwill=Decimal(str(report_data.get("goodwill", "0"))),
        cash_and_equivalents=Decimal(str(report_data.get("cash_and_equivalents", "0"))),
        interest_bearing_debt=Decimal(
            str(report_data.get("interest_bearing_debt", "0"))
        ),
        report_source=str(report_data.get("report_source", "AKShare")),
    )
    db_report = await financial_repo.create(fr_create)
    logger.info(f"Created financial report for {ticker} period={period_str}")
    return UUID(str(db_report.report_id))
