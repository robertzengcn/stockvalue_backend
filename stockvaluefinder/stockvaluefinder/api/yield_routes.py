"""Yield gap analysis API endpoints."""

from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from stockvaluefinder.api.dependencies import get_initialized_data_service
from stockvaluefinder.external.data_service import ExternalDataService
from stockvaluefinder.external.rate_client import RateClient
from stockvaluefinder.models.api import ApiResponse
from stockvaluefinder.models.enums import Market
from stockvaluefinder.models.yield_gap import YieldGap
from stockvaluefinder.services.yield_service import YieldAnalyzer
from stockvaluefinder.utils.errors import DataValidationError, ExternalAPIError

router = APIRouter(prefix="/api/v1/analyze/yield", tags=["yield"])


class YieldAnalysisRequest(BaseModel):
    """Request model for yield gap analysis."""

    ticker: str = Field(
        ...,
        pattern=r"^\d{6}\.(SH|SZ|HK)$",
        description="Stock code (e.g., '600519.SH', '0700.HK')",
    )
    cost_basis: Decimal = Field(
        ...,
        gt=0,
        description="Purchase price per share (for calculating yield based on cost)",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {"ticker": "0700.HK", "cost_basis": 300.00},
                {"ticker": "600519.SH", "cost_basis": 1800.00},
            ]
        }


@router.post("/", response_model=ApiResponse[YieldGap])
async def analyze_yield(
    request: YieldAnalysisRequest,
    data_service: ExternalDataService = Depends(get_initialized_data_service),
) -> ApiResponse[YieldGap]:
    """Analyze yield gap for a given stock.

    Calculates tax-aware dividend yield and compares against risk-free rates
    (10-year treasury bond and 3-year large deposit) to determine if dividend
    stock is attractive vs. risk-free investment.

    Args:
        request: Yield analysis request with ticker and cost_basis
        db: Database session
        data_service: External data service for fetching financial data

    Returns:
        ApiResponse with YieldGap data

    Raises:
        404: If stock not found
        400: If price/dividend data not available
        500: For server errors
    """
    try:
        # Normalize ticker
        ticker = request.ticker.upper()

        # Determine market from ticker suffix
        if ticker.endswith(".HK"):
            market = Market.HK_SHARE
        else:
            market = Market.A_SHARE

        # Fetch actual data from Tushare/AKShare
        current_price = await data_service.get_current_price(ticker)
        gross_dividend_yield = await data_service.get_dividend_yield(ticker)

        # Fetch risk-free rates
        rate_client = RateClient()
        risk_free_bond_rate = await rate_client.get_10y_treasury_yield()
        risk_free_deposit_rate = await rate_client.get_3y_deposit_rate()

        # Analyze yield gap
        analyzer = YieldAnalyzer()
        yield_gap = analyzer.analyze(
            ticker=ticker,
            cost_basis=request.cost_basis,
            current_price=current_price,
            gross_dividend_yield=gross_dividend_yield,
            risk_free_bond_rate=risk_free_bond_rate,
            risk_free_deposit_rate=risk_free_deposit_rate,
            market=market,
            analysis_id=uuid4(),
        )

        # TODO: Save to database
        # await yield_repo.create(yield_gap)

        return ApiResponse(success=True, data=yield_gap)

    except DataValidationError as e:
        return ApiResponse(success=False, error=str(e))
    except ExternalAPIError as e:
        return ApiResponse(success=False, error=f"Failed to fetch market data: {e}")
    except Exception as e:
        return ApiResponse(success=False, error=f"Internal server error: {e}")
