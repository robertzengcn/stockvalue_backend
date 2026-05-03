"""ROIC-WACC Spread Analysis API endpoints."""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.api.dependencies import get_initialized_data_service
from stockvaluefinder.api.stock_helpers import ensure_stock_exists
from stockvaluefinder.config import settings
from stockvaluefinder.db.base import get_db
from stockvaluefinder.external.data_service import ExternalDataService
from stockvaluefinder.external.rate_client import RateClient
from stockvaluefinder.models.api import ApiResponse
from stockvaluefinder.models.enums import Market
from stockvaluefinder.models.roic import (
    MoatTrendResult,
    ROICAnalysisRequest,
    ROICAnalysisResult,
    ROICResultCreate,
    WACCBreakdown,
)
from stockvaluefinder.repositories.roic_repo import ROICResultRepository
from stockvaluefinder.repositories.stock_repo import StockRepository
from stockvaluefinder.services.roic_service import (
    analyze_roic_trend,
    calculate_invested_capital,
    calculate_nopat,
    calculate_roic,
    calculate_roic_wacc_spread,
    is_financial_sector,
)
from stockvaluefinder.services.risk_service import _to_float
from stockvaluefinder.services.valuation_service import calculate_wacc
from stockvaluefinder.utils.errors import DataValidationError, ExternalAPIError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analyze/roic", tags=["roic"])


@router.post("/", response_model=ApiResponse[ROICAnalysisResult])
async def analyze_roic(
    request: ROICAnalysisRequest,
    data_service: ExternalDataService = Depends(get_initialized_data_service),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ROICAnalysisResult]:
    """Analyze ROIC-WACC spread for a given stock.

    Performs full ROIC analysis: fetches financial data, detects sector,
    computes NOPAT/Invested Capital/ROIC/WACC/spread, runs 3-year trend,
    and persists results to PostgreSQL.

    Args:
        request: ROICAnalysisRequest with ticker and optional year.
        data_service: Injected ExternalDataService instance.
        db: Injected AsyncSession for database operations.

    Returns:
        ApiResponse wrapping ROICAnalysisResult with all computed metrics.
    """
    try:
        ticker = request.ticker.upper()

        # (a) Fetch current-year ROIC inputs (profit + balance sheet)
        roic_inputs = await data_service.get_roic_inputs(ticker, request.year)
        profit_data = roic_inputs.get("profit", {})
        balance_data = roic_inputs.get("balance", {})
        fiscal_year = roic_inputs.get("fiscal_year", request.year)

        # (b) Detect financial sector (D-09)
        market = Market.HK_SHARE if ticker.endswith(".HK") else Market.A_SHARE
        await ensure_stock_exists(ticker, market, data_service, db)
        stock_repo = StockRepository(db)
        stock = await stock_repo.get_by_ticker(ticker)
        is_fin = is_financial_sector(stock.industry) if stock else False

        # (c) Compute NOPAT (D-10)
        nopat, nopat_audit = calculate_nopat(profit_data, is_financial=is_fin)
        tax_rate = nopat_audit.get("tax_rate", 0.0)

        # (d) Compute Invested Capital (D-08, D-11)
        invested_capital, negative_ic = calculate_invested_capital(balance_data)

        # (e) Compute ROIC
        roic_value = calculate_roic(nopat, invested_capital, negative_ic)

        # (f) Compute WACC with debt weighting (D-01, D-02, D-03)
        rate_client = RateClient()
        try:
            rf = await rate_client.get_10y_treasury_yield()
        except Exception:
            logger.warning(
                "Failed to fetch treasury yield for %s, using default",
                ticker,
                exc_info=True,
            )
            rf = 0.025  # 2.5% default

        beta = float(profit_data.get("beta", settings.valuation.DEFAULT_BETA))
        erp = settings.valuation.DEFAULT_MARKET_RISK_PREMIUM
        ke = rf + beta * erp

        # Compute Kd from finance expense and total debt (D-02)
        finance_expense = _to_float(
            profit_data.get("FINANCE_EXPENSE"), "FINANCE_EXPENSE"
        )
        total_equity = _to_float(
            balance_data.get("TOTAL_PARENT_EQUITY"), "TOTAL_PARENT_EQUITY"
        )
        short_debt = _to_float(balance_data.get("SHORT_LOAN"), "SHORT_LOAN")
        long_debt = _to_float(balance_data.get("LONG_LOAN"), "LONG_LOAN")
        bonds = _to_float(balance_data.get("BOND_PAYABLE"), "BOND_PAYABLE")
        total_debt = short_debt + long_debt + bonds

        kd: float | None = None
        if total_debt > 0 and finance_expense != 0:
            kd = abs(finance_expense) / total_debt

        # Compute debt weight (D-03)
        capital_base = total_equity + total_debt
        debt_weight: float = 0.0
        if capital_base > 0:
            debt_weight = total_debt / capital_base
        equity_weight = 1.0 - debt_weight

        # D/E ratio
        de_ratio: float | None = None
        if total_equity > 0:
            de_ratio = total_debt / total_equity

        wacc_value = calculate_wacc(
            rf,
            beta,
            erp,
            debt_weight=debt_weight,
            cost_of_debt=kd or 0.0,
            tax_rate=tax_rate,
        )

        wacc_breakdown = WACCBreakdown(
            ke=round(ke, 6),
            kd=round(kd, 6) if kd is not None else None,
            equity_weight=round(equity_weight, 6),
            debt_weight=round(debt_weight, 6),
            de_ratio=round(de_ratio, 6) if de_ratio is not None else None,
            tax_rate=round(tax_rate, 6) if tax_rate != 0.0 else None,
            wacc=round(wacc_value, 6),
        )

        # (g) Compute spread (D-03)
        spread, classification = calculate_roic_wacc_spread(roic_value, wacc_value)

        # (h) Compute 3-year trend (D-06)
        moat_trend_result: MoatTrendResult | None = None
        try:
            multi_year = await data_service.get_multi_year_roic_inputs(ticker, years=3)

            # For each year, compute spread using same logic
            yearly_spreads: list[float | None] = []
            yearly_fiscal_years: list[int] = []
            for year_entry in multi_year:
                yr_profit = year_entry.get("profit", {})
                yr_balance = year_entry.get("balance", {})
                yr_fy = year_entry.get("fiscal_year")

                if yr_fy is None:
                    continue

                yr_nopat, _ = calculate_nopat(yr_profit, is_financial=is_fin)
                yr_ic, yr_neg_ic = calculate_invested_capital(yr_balance)
                yr_roic = calculate_roic(yr_nopat, yr_ic, yr_neg_ic)

                # Use same WACC for all years (current year WACC)
                yr_spread, _ = calculate_roic_wacc_spread(yr_roic, wacc_value)

                yearly_spreads.append(yr_spread)
                yearly_fiscal_years.append(yr_fy)

            if yearly_spreads:
                trend_data = analyze_roic_trend(yearly_spreads, yearly_fiscal_years)
                moat_trend_result = MoatTrendResult(
                    trend=trend_data["trend"],
                    slope=trend_data.get("slope"),
                    p_value=trend_data.get("p_value"),
                    data_points=trend_data["data_points"],
                )
        except Exception:
            logger.warning(
                "Failed to compute moat trend for %s",
                ticker,
                exc_info=True,
            )

        # (i) Build response
        audit_trail: dict[str, object] = {
            "nopat": nopat_audit,
            "invested_capital": {
                "value": invested_capital,
                "negative_ic": negative_ic,
            },
            "wacc": wacc_breakdown.model_dump(),
            "sector": {
                "industry": stock.industry if stock else "Unknown",
                "is_financial": is_fin,
            },
        }

        result = ROICAnalysisResult(
            ticker=ticker,
            fiscal_year=fiscal_year if fiscal_year is not None else 0,
            roic=roic_value,
            negative_invested_capital=negative_ic,
            nopat=nopat,
            invested_capital=invested_capital,
            wacc_breakdown=wacc_breakdown,
            spread=spread,
            spread_classification=classification,
            moat_trend=moat_trend_result,
            is_financial_sector=is_fin,
            audit_trail=audit_trail,
            calculated_at=datetime.now(timezone.utc),
        )

        # (j) Persist to database (non-blocking)
        try:
            roic_repo = ROICResultRepository(db)
            create_data = ROICResultCreate(
                analysis_id=uuid4(),
                ticker=ticker,
                fiscal_year=result.fiscal_year,
                roic=result.roic,
                negative_invested_capital=result.negative_invested_capital,
                nopat=result.nopat,
                invested_capital=result.invested_capital,
                wacc=result.wacc_breakdown.wacc,
                wacc_breakdown=result.wacc_breakdown.model_dump(),
                spread=result.spread,
                spread_classification=result.spread_classification.value,
                moat_trend=(
                    moat_trend_result.model_dump() if moat_trend_result else None
                ),
                is_financial_sector=result.is_financial_sector,
                audit_trail=result.audit_trail,
            )
            await roic_repo.upsert_by_ticker_year(create_data)
            await db.commit()
            logger.info("Successfully saved ROIC analysis for %s to database", ticker)
        except Exception as db_error:
            await db.rollback()
            logger.error("Failed to save ROIC analysis for %s: %s", ticker, db_error)

        return ApiResponse(success=True, data=result)

    except DataValidationError as e:
        logger.warning("Data validation error for %s: %s", request.ticker, e)
        return ApiResponse(success=False, error=str(e))
    except ExternalAPIError as e:
        logger.error("External API error for %s: %s", request.ticker, e)
        return ApiResponse(
            success=False,
            error="Failed to fetch financial data. Please try again later.",
        )
    except Exception:
        logger.exception("Unexpected error in ROIC analysis for %s", request.ticker)
        return ApiResponse(
            success=False,
            error="An internal error occurred. Please try again later.",
        )
