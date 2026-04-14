"""DCF Valuation API endpoints."""

import asyncio
import logging
from decimal import Decimal
from typing import cast
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.api.dependencies import get_initialized_data_service
from stockvaluefinder.api.stock_helpers import ensure_stock_exists
from stockvaluefinder.config import settings
from stockvaluefinder.db.base import get_db
from stockvaluefinder.repositories.stock_repo import StockRepository
from stockvaluefinder.external.data_service import ExternalDataService
from stockvaluefinder.external.rate_client import RateClient
from stockvaluefinder.models.api import ApiResponse
from stockvaluefinder.models.enums import Market
from stockvaluefinder.models.narrative import (
    ValuationResultWithNarrative,
    generate_and_serialize_narrative,
)
from stockvaluefinder.models.valuation import (
    DCFExplanationRequest,
    DCFExplanationResponse,
    DCFParams,
    DCFValuationRequest,
    ValuationResultCreate,
)
from stockvaluefinder.repositories.valuation_repo import ValuationRepository
from stockvaluefinder.services.narrative_prompts import build_valuation_prompt
from stockvaluefinder.services.narrative_service import get_narrative_service
from stockvaluefinder.services.valuation_service import DCFValuationService
from stockvaluefinder.utils.errors import DataValidationError, ExternalAPIError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analyze/dcf", tags=["valuation"])


@router.post("/", response_model=ApiResponse[ValuationResultWithNarrative])
async def analyze_dcf(
    request: DCFValuationRequest,
    data_service: ExternalDataService = Depends(get_initialized_data_service),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ValuationResultWithNarrative]:
    """Analyze DCF valuation for a given stock.

    Performs Discounted Cash Flow analysis to calculate intrinsic value
    with two-stage growth model and Gordon Growth terminal value.
    """
    try:
        # Normalize ticker
        ticker = request.ticker.upper()

        # Fetch data in parallel for better performance
        rate_client = RateClient()

        # Prepare parallel tasks
        tasks = [
            data_service.get_current_price(ticker),
            data_service.get_free_cash_flow(ticker),
            data_service.get_shares_outstanding(ticker),
        ]

        # Only fetch risk-free rate if not provided
        if request.risk_free_rate is None:
            tasks.append(rate_client.get_10y_treasury_yield())

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results[:3]:
            if isinstance(result, Exception):
                raise result

        current_price = cast(Decimal, results[0])
        base_fcf = cast(float, results[1])
        shares_outstanding = cast(float, results[2])

        # Handle risk-free rate result
        if request.risk_free_rate is None:
            rf_res = results[3]
            if isinstance(rf_res, Exception):
                raise rf_res
            risk_free_rate = cast(float, rf_res)
        else:
            risk_free_rate = request.risk_free_rate

        # Use provided or default beta
        beta = (
            request.beta
            if request.beta is not None
            else settings.valuation.DEFAULT_BETA
        )

        # Use provided or default market risk premium
        market_risk_premium = (
            request.market_risk_premium
            if request.market_risk_premium is not None
            else settings.valuation.DEFAULT_MARKET_RISK_PREMIUM
        )

        # Build DCF parameters
        dcf_params = DCFParams(
            growth_rate_stage1=request.growth_rate_stage1,
            growth_rate_stage2=request.growth_rate_stage2,
            years_stage1=request.years_stage1,
            years_stage2=request.years_stage2,
            terminal_growth=request.terminal_growth,
            risk_free_rate=risk_free_rate,
            beta=beta,
            market_risk_premium=market_risk_premium,
        )

        # Analyze DCF valuation
        service = DCFValuationService()
        valuation = service.analyze(
            ticker=ticker,
            current_price=current_price,
            base_fcf=base_fcf,
            shares_outstanding=shares_outstanding,
            dcf_params=dcf_params,
            valuation_id=uuid4(),
        )

        # Generate LLM narrative (graceful fallback to None on failure)
        narrative_svc = get_narrative_service()
        narrative, narrative_json = await generate_and_serialize_narrative(
            ticker=ticker,
            result_data=valuation.model_dump(),
            prompt_builder=build_valuation_prompt,
            narrative_svc=narrative_svc,
        )

        # Save to database with explicit transaction handling
        try:
            market = Market.HK_SHARE if ticker.endswith(".HK") else Market.A_SHARE
            await ensure_stock_exists(ticker, market, data_service, db)

            valuation_repo = ValuationRepository(db)
            valuation_create = ValuationResultCreate(
                valuation_id=valuation.valuation_id,
                ticker=valuation.ticker,
                current_price=valuation.current_price,
                intrinsic_value=valuation.intrinsic_value,
                wacc=valuation.wacc,
                margin_of_safety=valuation.margin_of_safety,
                valuation_level=valuation.valuation_level,
                calculated_at=valuation.calculated_at,
                dcf_params=valuation.dcf_params,
                audit_trail=valuation.audit_trail,
                narrative=narrative_json,
            )
            await valuation_repo.create(valuation_create)
            await db.commit()
            logger.info(f"Successfully saved DCF valuation for {ticker} to database")
        except Exception as db_error:
            await db.rollback()
            logger.error(f"Failed to save valuation for {ticker}: {db_error}")

        # Fetch stock name: try external API first, fall back to DB
        stock_name: str | None = None
        try:
            info_records = await data_service.get_stock_basic(ts_code=ticker)
            if isinstance(info_records, list) and len(info_records) > 1:
                info_map = {
                    r.get("item", ""): r.get("value", "")
                    for r in info_records
                    if isinstance(r, dict)
                }
                stock_name = str(
                    info_map.get("股票简称", info_map.get("公司名称", None))
                )
            elif isinstance(info_records, list) and info_records:
                stock_name = str(info_records[0].get("name", None))
        except Exception:
            logger.warning(f"External API failed for stock name of {ticker}")

        # Fallback: read name from DB (ensure_stock_exists saved it earlier)
        if stock_name is None or stock_name == "None":
            try:
                stock_repo = StockRepository(db)
                stock_db = await stock_repo.get_by_ticker(ticker)
                if stock_db is not None and stock_db.name != ticker:
                    stock_name = stock_db.name
            except Exception:
                logger.warning(f"DB fallback also failed for stock name of {ticker}")

        result = ValuationResultWithNarrative(
            **valuation.model_dump(),
            stock_name=stock_name,
            narrative=narrative,
        )

        return ApiResponse(success=True, data=result, error=None, meta=None)

    except DataValidationError as e:
        logger.warning(f"Data validation error for {ticker}: {e}")
        return ApiResponse(success=False, data=None, error=str(e), meta=None)
    except ExternalAPIError as e:
        logger.error(f"External API error for {ticker}: {e}")
        return ApiResponse(
            success=False,
            data=None,
            error="Failed to fetch market data. Please try again later.",
            meta=None,
        )
    except Exception:
        logger.exception(f"Unexpected error in DCF analysis for {ticker}")
        return ApiResponse(
            success=False,
            data=None,
            error="An internal error occurred. Please try again later.",
            meta=None,
        )


@router.post("/explain", response_model=ApiResponse[DCFExplanationResponse])
async def explain_dcf(
    request: DCFExplanationRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[DCFExplanationResponse]:
    """Generate AI explanation for a previously stored DCF valuation.

    Fetches the stored valuation result (with full audit trail) by its
    valuation_id and uses the LLM to produce a step-by-step explanation
    of how the intrinsic value was calculated.
    """
    valuation_id = request.valuation_id

    try:
        # Fetch stored valuation from DB
        valuation_repo = ValuationRepository(db)
        db_result = await valuation_repo.get_by_valuation_id(valuation_id)

        if db_result is None:
            return ApiResponse(
                success=False,
                data=None,
                error=f"Valuation result not found for id: {valuation_id}",
                meta=None,
            )

        # Reconstruct result data for LLM prompt (include audit_trail)
        result_data = {
            "ticker": db_result.ticker,
            "current_price": float(db_result.current_price),
            "intrinsic_value": float(db_result.intrinsic_value),
            "wacc": db_result.wacc,
            "margin_of_safety": db_result.margin_of_safety,
            "valuation_level": db_result.valuation_level,
            "dcf_params": db_result.dcf_params,
            "audit_trail": db_result.audit_trail,
        }

        # Generate DCF explanation via LLM (graceful fallback to None)
        narrative_svc = get_narrative_service()
        explanation = await narrative_svc.generate_dcf_explanation(
            ticker=db_result.ticker,
            result_data=result_data,
        )

        # Fetch stock name from DB
        stock_name: str | None = None
        try:
            stock_repo = StockRepository(db)
            stock_db = await stock_repo.get_by_ticker(db_result.ticker)
            if stock_db is not None and stock_db.name != db_result.ticker:
                stock_name = stock_db.name
        except Exception:
            logger.warning(f"Failed to fetch stock name for {db_result.ticker}")

        response = DCFExplanationResponse(
            valuation_id=valuation_id,
            ticker=db_result.ticker,
            stock_name=stock_name,
            current_price=float(db_result.current_price),
            intrinsic_value=float(db_result.intrinsic_value),
            valuation_level=db_result.valuation_level,
            explanation=explanation,
        )

        return ApiResponse(success=True, data=response, error=None, meta=None)

    except Exception:
        logger.exception(f"Unexpected error in DCF explanation for {valuation_id}")
        return ApiResponse(
            success=False,
            data=None,
            error="An internal error occurred. Please try again later.",
            meta=None,
        )
