"""DCF Valuation API endpoints."""

import asyncio
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.api.dependencies import get_initialized_data_service
from stockvaluefinder.config import settings
from stockvaluefinder.db.base import get_db
from stockvaluefinder.external.data_service import ExternalDataService
from stockvaluefinder.external.rate_client import RateClient
from stockvaluefinder.models.api import ApiResponse
from stockvaluefinder.models.valuation import (
    DCFParams,
    DCFValuationRequest,
    ValuationResult,
    ValuationResultCreate,
)
from stockvaluefinder.repositories.valuation_repo import ValuationRepository
from stockvaluefinder.services.valuation_service import DCFValuationService
from stockvaluefinder.utils.errors import DataValidationError, ExternalAPIError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analyze/dcf", tags=["valuation"])


@router.post("/", response_model=ApiResponse[ValuationResult])
async def analyze_dcf(
    request: DCFValuationRequest,
    data_service: ExternalDataService = Depends(get_initialized_data_service),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ValuationResult]:
    """Analyze DCF valuation for a given stock.

    Performs Discounted Cash Flow analysis to calculate intrinsic value
    with two-stage growth model and Gordon Growth terminal value.

    Args:
        request: DCF valuation request with ticker and parameters
        db: Database session
        data_service: External data service for fetching financial data

    Returns:
        ApiResponse with ValuationResult data including full audit trail
    """
    try:
        # Normalize ticker
        ticker = request.ticker.upper()

        # Fetch data in parallel for better performance
        # Get risk-free rate (use provided or fetch current)
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
        current_price = results[0]
        base_fcf = results[1]
        shares_outstanding = results[2]

        # Handle risk-free rate result
        if request.risk_free_rate is None:
            if isinstance(results[3], Exception):
                raise results[3]
            risk_free_rate = results[3]
        else:
            risk_free_rate = request.risk_free_rate

        # Check for errors in parallel tasks
        for result in results[:3]:
            if isinstance(result, Exception):
                raise result

        # Use provided or default beta
        beta = request.beta if request.beta is not None else settings.valuation.DEFAULT_BETA

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

        # Save to database with explicit transaction handling
        try:
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
            )
            await valuation_repo.create(valuation_create)
            await db.commit()
            logger.info(f"Successfully saved DCF valuation for {ticker} to database")
        except Exception as db_error:
            await db.rollback()
            logger.error(f"Failed to save valuation for {ticker}: {db_error}")
            # Still return the valuation result, but log the database error
            # The analysis succeeded even if persistence failed

        return ApiResponse(success=True, data=valuation)

    except DataValidationError as e:
        logger.warning(f"Data validation error for {ticker}: {e}")
        return ApiResponse(success=False, error=str(e))
    except ExternalAPIError as e:
        logger.error(f"External API error for {ticker}: {e}")
        return ApiResponse(success=False, error="Failed to fetch market data. Please try again later.")
    except Exception as e:
        logger.exception(f"Unexpected error in DCF analysis for {ticker}")
        return ApiResponse(success=False, error="An internal error occurred. Please try again later.")
