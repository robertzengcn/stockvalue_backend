"""Risk analysis API endpoints."""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.api.dependencies import get_initialized_data_service
from stockvaluefinder.db.base import get_db
from stockvaluefinder.external.data_service import ExternalDataService
from stockvaluefinder.models.api import ApiResponse
from stockvaluefinder.models.risk import RiskScore
from stockvaluefinder.repositories.risk_repo import RiskScoreRepository
from stockvaluefinder.services.risk_service import RiskAnalyzer
from stockvaluefinder.utils.errors import DataValidationError, ExternalAPIError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analyze/risk", tags=["risk"])


class RiskAnalysisRequest(BaseModel):
    """Request model for risk analysis."""

    ticker: str = Field(
        ...,
        pattern=r"^\d{6}\.(SH|SZ|HK)$",
        description="Stock code (e.g., '600519.SH', '0700.HK')",
    )
    year: int | None = Field(
        None,
        ge=2000,
        le=2099,
        description="Fiscal year for analysis (defaults to most recent)",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {"ticker": "600519.SH"},
                {"ticker": "0700.HK", "year": 2023},
                {"ticker": "000002.SZ"},
            ]
        }


@router.post("/", response_model=ApiResponse[RiskScore])
async def analyze_risk(
    request: RiskAnalysisRequest,
    data_service: ExternalDataService = Depends(get_initialized_data_service),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[RiskScore]:
    """Analyze financial risk for a given stock.

    Performs comprehensive financial fraud detection including:
    - Beneish M-Score for earnings manipulation
    - 存贷双高
    - Goodwill ratio analysis
    - Profit vs cash flow divergence detection

    Args:
        request: Risk analysis request with ticker and optional year
        db: Database session
        data_service: External data service for fetching financial data

    Returns:
        ApiResponse with RiskScore data

    Raises:
        404: If stock not found
        400: If financial data not available
        500: For server errors
    """
    try:
        # Normalize ticker
        ticker = request.ticker.upper()

        # Fetch actual financial data from Tushare/AKShare
        # Get current year's report
        current_year = request.year

        # Fetch both years in parallel for better performance
        current_year_param = current_year if current_year else None

        # We need to fetch current year first to determine previous year
        current_report = await data_service.get_financial_report(
            ticker, current_year_param
        )

        # Get previous year's report for YoY comparison
        previous_year = (
            current_report["fiscal_year"] - 1
            if current_year is None
            else current_year - 1
        )

        # Fetch previous year report
        previous_report = await data_service.get_financial_report(ticker, previous_year)

        # Analyze risk
        analyzer = RiskAnalyzer()
        risk_score = analyzer.analyze(current_report, previous_report)

        # Save to database with explicit transaction handling
        try:
            risk_repo = RiskScoreRepository(db)
            # Convert RiskScore to RiskScoreCreate for persistence
            from stockvaluefinder.models.risk import RiskScoreCreate
            from uuid import uuid4

            risk_create = RiskScoreCreate(
                risk_id=uuid4(),
                ticker=ticker,
                fiscal_year=current_report["fiscal_year"],
                beneish_m_score=risk_score.beneish_m_score,
                manipulation_probability=risk_score.manipulation_probability,
                high_cash_high_debt=risk_score.high_cash_high_debt,
                goodwill_ratio=risk_score.goodwill_ratio,
                profit_cash_divergence=risk_score.profit_cash_divergence,
                overall_risk_level=risk_score.overall_risk_level,
                risk_flags=risk_score.risk_flags,
                calculated_at=risk_score.calculated_at,
            )
            await risk_repo.create(risk_create)
            await db.commit()
            logger.info(f"Successfully saved risk analysis for {ticker} to database")
        except Exception as db_error:
            await db.rollback()
            logger.error(f"Failed to save risk analysis for {ticker}: {db_error}")
            # Still return the result, but log the database error

        return ApiResponse(success=True, data=risk_score)

    except DataValidationError as e:
        logger.warning(f"Data validation error for {request.ticker}: {e}")
        return ApiResponse(success=False, error=str(e))
    except ExternalAPIError as e:
        logger.error(f"External API error for {request.ticker}: {e}")
        return ApiResponse(
            success=False,
            error="Failed to fetch financial data. Please try again later.",
        )
    except Exception:
        logger.exception(f"Unexpected error in risk analysis for {request.ticker}")
        return ApiResponse(
            success=False, error="An internal error occurred. Please try again later."
        )
