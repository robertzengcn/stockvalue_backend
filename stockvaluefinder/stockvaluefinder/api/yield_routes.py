"""Yield gap analysis API endpoints."""

import asyncio
import logging
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.api.dependencies import get_initialized_data_service
from stockvaluefinder.db.base import get_db
from stockvaluefinder.external.data_service import ExternalDataService
from stockvaluefinder.external.rate_client import RateClient
from stockvaluefinder.models.api import ApiResponse
from stockvaluefinder.models.enums import Market
from stockvaluefinder.models.yield_gap import YieldGap
from stockvaluefinder.repositories.yield_repo import YieldGapRepository
from stockvaluefinder.services.yield_service import YieldAnalyzer
from stockvaluefinder.utils.errors import DataValidationError, ExternalAPIError

logger = logging.getLogger(__name__)
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
    db: AsyncSession = Depends(get_db),
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

        # Fetch data in parallel for better performance
        rate_client = RateClient()

        # Execute all API calls concurrently
        results = await asyncio.gather(
            data_service.get_current_price(ticker),
            data_service.get_dividend_yield(ticker),
            rate_client.get_10y_treasury_yield(),
            rate_client.get_3y_deposit_rate(),
            return_exceptions=True,
        )

        # Process results
        (
            current_price,
            gross_dividend_yield,
            risk_free_bond_rate,
            risk_free_deposit_rate,
        ) = results

        # Check for errors and narrow types
        from typing import cast

        if isinstance(current_price, Exception):
            raise current_price
        if isinstance(gross_dividend_yield, Exception):
            raise gross_dividend_yield
        if isinstance(risk_free_bond_rate, Exception):
            raise risk_free_bond_rate
        if isinstance(risk_free_deposit_rate, Exception):
            raise risk_free_deposit_rate

        current_price = cast("Decimal", current_price)
        gross_dividend_yield = cast("float", gross_dividend_yield)
        risk_free_bond_rate = cast("float", risk_free_bond_rate)
        risk_free_deposit_rate = cast("float", risk_free_deposit_rate)

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

        # Save to database with explicit transaction handling
        try:
            yield_repo = YieldGapRepository(db)
            # Convert YieldGap to YieldGapCreate for persistence
            from stockvaluefinder.models.yield_gap import YieldGapCreate

            yield_create = YieldGapCreate(
                analysis_id=yield_gap.analysis_id,
                ticker=ticker,
                cost_basis=request.cost_basis,
                current_price=yield_gap.current_price,
                gross_dividend_yield=yield_gap.gross_dividend_yield,
                net_dividend_yield=yield_gap.net_dividend_yield,
                risk_free_bond_rate=yield_gap.risk_free_bond_rate,
                risk_free_deposit_rate=yield_gap.risk_free_deposit_rate,
                yield_gap=yield_gap.yield_gap,
                recommendation=yield_gap.recommendation,
                market=market,
                calculated_at=yield_gap.calculated_at,
            )
            await yield_repo.create(yield_create)
            await db.commit()
            logger.info(
                f"Successfully saved yield gap analysis for {ticker} to database"
            )
        except Exception as db_error:
            await db.rollback()
            logger.error(f"Failed to save yield gap analysis for {ticker}: {db_error}")
            # Still return the result, but log the database error

        return ApiResponse(success=True, data=yield_gap)

    except DataValidationError as e:
        logger.warning(f"Data validation error for {request.ticker}: {e}")
        return ApiResponse(success=False, error=str(e))
    except ExternalAPIError as e:
        logger.error(f"External API error for {request.ticker}: {e}")
        return ApiResponse(
            success=False, error="Failed to fetch market data. Please try again later."
        )
    except Exception:
        logger.exception(f"Unexpected error in yield gap analysis for {request.ticker}")
        return ApiResponse(
            success=False, error="An internal error occurred. Please try again later."
        )
