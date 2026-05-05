"""Capital Allocation Scorecard API endpoints."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.api.dependencies import get_initialized_data_service
from stockvaluefinder.api.stock_helpers import ensure_stock_exists
from stockvaluefinder.db.base import get_db
from stockvaluefinder.external.data_service import ExternalDataService
from stockvaluefinder.models.api import ApiResponse
from stockvaluefinder.models.capital_allocation import (
    BuybackYieldResult,
    CapitalAllocationGrade,
    CapitalAllocationRequest,
    CapitalAllocationResult,
    CapitalAllocationScoreCreate,
    DividendStabilityResult,
    ExpansionDisciplineResult,
)
from stockvaluefinder.models.enums import Market
from stockvaluefinder.repositories.capital_allocation_repo import (
    CapitalAllocationRepository,
)
from stockvaluefinder.repositories.dividend_repo import DividendRepository
from stockvaluefinder.repositories.roic_repo import ROICResultRepository
from stockvaluefinder.services.capex_service import (
    calculate_buyback_yield,
    calculate_capital_allocation_score,
    classify_dividend_stability,
    detect_blind_expansion,
    grade_buyback_yield,
    grade_dividend_stability,
    grade_expansion_discipline,
)
from stockvaluefinder.utils.errors import DataValidationError, ExternalAPIError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analyze/capex", tags=["capex"])


@router.post("/", response_model=ApiResponse[CapitalAllocationResult])
async def analyze_capital_allocation(
    request: CapitalAllocationRequest,
    data_service: ExternalDataService = Depends(get_initialized_data_service),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[CapitalAllocationResult]:
    """Analyze capital allocation scorecard for a given stock.

    Orchestrates three dimensions of capital allocation quality:
    1. Buyback yield (repurchase amount / market cap)
    2. Dividend stability (5-year DPU trend via scipy linregress)
    3. Expansion discipline (blind expansion = ROIC < WACC + CapEx surge)

    Returns combined A/B/C/D scorecard grade with equal weighting.

    Args:
        request: CapitalAllocationRequest with ticker and optional year.
        data_service: Injected ExternalDataService instance.
        db: Injected AsyncSession for database operations.

    Returns:
        ApiResponse wrapping CapitalAllocationResult with all computed metrics.
    """
    try:
        ticker = request.ticker.upper()

        # (a) Input validation and stock setup
        market = Market.HK_SHARE if ticker.endswith(".HK") else Market.A_SHARE
        await ensure_stock_exists(ticker, market, data_service, db)

        # Determine fiscal year: use request.year if provided, else current year - 1
        today = datetime.now(timezone.utc)
        fiscal_year: int = request.year if request.year else today.year - 1

        # =====================================================================
        # (b) Buyback yield dimension (CAPEX-01, D-01, D-02)
        # =====================================================================
        buyback_data = await data_service.get_buyback_data(ticker)

        # Get market cap from price * shares outstanding
        market_cap: float | None = None
        try:
            price: Decimal = await data_service.get_current_price(ticker)
            shares: float = await data_service.get_shares_outstanding(ticker)
            market_cap = float(price) * shares
        except Exception:
            logger.warning("Failed to compute market cap for %s, using None", ticker)

        buyback_yield_value = calculate_buyback_yield(
            buyback_data.get("repurchase_amount"), market_cap
        )
        buyback_grade = grade_buyback_yield(buyback_yield_value)
        buyback_yield_result = BuybackYieldResult(
            buyback_yield=buyback_yield_value,
            repurchase_amount=buyback_data.get("repurchase_amount"),
            market_cap=market_cap,
            data_quality=buyback_data.get("data_quality", "NO_DATA"),
            grade=buyback_grade,
        )

        # =====================================================================
        # (c) Dividend stability dimension (CAPEX-02, D-03, D-04)
        # =====================================================================
        # DB-first per D-03: check DividendDataDB for 5-year DPU data
        dividend_repo = DividendRepository(db)
        dividend_records = await dividend_repo.get_by_ticker(ticker, limit=10)

        # Extract DPU values from DB records, group by fiscal_year,
        # sum dividend_per_share per year
        dpu_by_year: dict[int, float] = {}
        for record in dividend_records:
            if record.fiscal_year is not None:
                fy = int(record.fiscal_year)
                dpu_by_year[fy] = dpu_by_year.get(fy, 0.0) + float(
                    record.dividend_per_share
                )

        # Sort by year ascending and build parallel lists
        sorted_years = sorted(dpu_by_year.keys())
        dpu_values: list[float | None] = [dpu_by_year[yr] for yr in sorted_years]
        dpu_years: list[int] = sorted_years

        # If fewer than 3 years of DB data, fall back to AKShare per D-03
        if len(dpu_values) < 3:
            try:
                if data_service._akshare is not None:
                    symbol = ticker.split(".")[0] if "." in ticker else ticker
                    akshare_dividends = (
                        await data_service._akshare.get_dividend_history(symbol)
                    )
                    if akshare_dividends:
                        # Parse AKShare dividend history into DPU by year
                        ak_dpu_by_year: dict[int, float] = {}
                        for entry in akshare_dividends:
                            # AKShare dividend history has year or fiscal_year
                            fy_raw = entry.get("year") or entry.get("fiscal_year")
                            dpu_raw = entry.get("dividend_per_share") or entry.get(
                                "每股派息"
                            )
                            if fy_raw is not None and dpu_raw is not None:
                                try:
                                    fy = int(fy_raw)
                                    dpu = float(dpu_raw)
                                    if dpu > 0:
                                        ak_dpu_by_year[fy] = (
                                            ak_dpu_by_year.get(fy, 0.0) + dpu
                                        )
                                except (ValueError, TypeError):
                                    continue

                        ak_sorted_years = sorted(ak_dpu_by_year.keys())
                        dpu_values = [ak_dpu_by_year[yr] for yr in ak_sorted_years]
                        dpu_years = ak_sorted_years
            except Exception:
                logger.warning(
                    "AKShare dividend fallback failed for %s",
                    ticker,
                    exc_info=True,
                )

        trend_data = classify_dividend_stability(dpu_values, dpu_years)
        dividend_grade = grade_dividend_stability(trend_data["classification"])
        dividend_stability_result = DividendStabilityResult(
            classification=trend_data["classification"],
            slope=trend_data.get("slope"),
            p_value=trend_data.get("p_value"),
            data_points=trend_data.get("data_points", 0),
            dpu_values=dpu_values,
            grade=dividend_grade,
        )

        # =====================================================================
        # (d) Expansion discipline dimension (CAPEX-03, D-05, D-06)
        # =====================================================================
        # Get ROIC from Phase 9 database per D-05
        roic_repo = ROICResultRepository(db)
        roic_result = await roic_repo.get_latest_for_ticker(ticker)

        roic_value: float | None = None
        wacc_value: float = 0.0
        if roic_result is not None:
            roic_value = roic_result.roic
            wacc_value = roic_result.wacc
        else:
            logger.info(
                "No ROIC result for %s, expansion discipline will use "
                "INSUFFICIENT_DATA",
                ticker,
            )

        # Get 2-year CapEx data per D-06
        capex_data = await data_service.get_multi_year_capex(ticker, years=2)

        capex_current: float | None = None
        capex_previous: float | None = None
        if len(capex_data) >= 2:
            # Sorted by fiscal_year descending: index 0 = current, 1 = previous
            capex_current = capex_data[0].get("capex")
            capex_previous = capex_data[1].get("capex")

        blind_expansion = detect_blind_expansion(
            roic_value, wacc_value, capex_current, capex_previous
        )
        expansion_grade = grade_expansion_discipline(blind_expansion)
        expansion_discipline_result = ExpansionDisciplineResult(
            alert=blind_expansion["alert"],
            roic_wacc_spread=blind_expansion.get("roic_wacc_spread"),
            capex_yoy_growth=blind_expansion.get("capex_yoy_growth"),
            capex_current=blind_expansion.get("capex_current"),
            capex_previous=blind_expansion.get("capex_previous"),
            reason=blind_expansion.get("reason"),
            grade=expansion_grade,
        )

        # =====================================================================
        # (e) Combined scorecard (CAPEX-04, D-07, D-08)
        # =====================================================================
        # Pass None for buyback_grade only when NO_DATA (no buyback programs)
        buyback_grade_for_score: CapitalAllocationGrade | None = (
            buyback_grade if buyback_data.get("data_quality") != "NO_DATA" else None
        )
        overall_grade, weighting = calculate_capital_allocation_score(
            buyback_grade_for_score, dividend_grade, expansion_grade
        )

        # =====================================================================
        # (f) Build response
        # =====================================================================
        result = CapitalAllocationResult(
            ticker=ticker,
            fiscal_year=fiscal_year,
            buyback_yield=buyback_yield_result,
            dividend_stability=dividend_stability_result,
            expansion_discipline=expansion_discipline_result,
            overall_grade=overall_grade,
            weighting=weighting,
            audit_trail={
                "buyback_data_source": buyback_data.get("data_quality"),
                "dividend_data_source": (
                    "db" if len(dividend_records) >= 3 else "akshare_fallback"
                ),
                "roic_data_source": ("phase9_db" if roic_result else "unavailable"),
                "capex_data_points": len(capex_data),
            },
            calculated_at=datetime.now(timezone.utc),
        )

        # =====================================================================
        # (g) Persist to database (non-blocking)
        # =====================================================================
        try:
            capex_repo = CapitalAllocationRepository(db)
            create_data = CapitalAllocationScoreCreate(
                analysis_id=uuid4(),
                ticker=ticker,
                fiscal_year=fiscal_year,
                buyback_yield_data=buyback_yield_result.model_dump(),
                dividend_stability_data=dividend_stability_result.model_dump(),
                expansion_discipline_data=(expansion_discipline_result.model_dump()),
                overall_grade=overall_grade.value,
                weighting=weighting,
                audit_trail=result.audit_trail,
            )
            await capex_repo.upsert_by_ticker_year(create_data)
            await db.commit()
            logger.info(
                "Successfully saved capital allocation analysis for %s to database",
                ticker,
            )
        except Exception as db_error:
            await db.rollback()
            logger.error(
                "Failed to save capital allocation analysis for %s: %s",
                ticker,
                db_error,
            )

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
        logger.exception(
            "Unexpected error in capital allocation analysis for %s",
            request.ticker,
        )
        return ApiResponse(
            success=False,
            error="An internal error occurred. Please try again later.",
        )
