"""DCF Valuation API endpoints."""

from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.api.dependencies import get_initialized_data_service
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

        # Fetch actual data from Tushare/AKShare
        current_price = await data_service.get_current_price(ticker)
        base_fcf = await data_service.get_free_cash_flow(ticker)
        shares_outstanding = await data_service.get_shares_outstanding(ticker)

        # Get risk-free rate (use provided or fetch current)
        rate_client = RateClient()
        risk_free_rate = (
            request.risk_free_rate
            if request.risk_free_rate is not None
            else await rate_client.get_10y_treasury_yield()
        )

        # Use provided or default beta
        beta = request.beta if request.beta is not None else 1.0

        # Use provided or default market risk premium
        market_risk_premium = (
            request.market_risk_premium
            if request.market_risk_premium is not None
            else 0.06
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

        # Save to database
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

        return ApiResponse(success=True, data=valuation)

    except DataValidationError as e:
        return ApiResponse(success=False, error=str(e))
    except ExternalAPIError as e:
        return ApiResponse(success=False, error=f"Failed to fetch market data: {e}")
    except Exception as e:
        return ApiResponse(success=False, error=f"Internal server error: {e}")
