"""Risk analysis API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from stockvaluefinder.api.dependencies import get_initialized_data_service
from stockvaluefinder.external.data_service import ExternalDataService
from stockvaluefinder.models.api import ApiResponse
from stockvaluefinder.models.risk import RiskScore
from stockvaluefinder.services.risk_service import RiskAnalyzer
from stockvaluefinder.utils.errors import DataValidationError, ExternalAPIError

router = APIRouter(prefix="/api/v1/analyze/risk", tags=["risk"])


class RiskAnalysisRequest(BaseModel):
    """Request model for risk analysis."""

    ticker: str = Field(
        ...,
        pattern=r"^\d{6}\.(SH|SZ|HK)$",
        description="Stock code (e.g., '600519.SH', '0700.HK')",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {"ticker": "600519.SH"},
                {"ticker": "0700.HK"},
                {"ticker": "000002.SZ"},
            ]
        }


@router.post("/", response_model=ApiResponse[RiskScore])
async def analyze_risk(
    request: RiskAnalysisRequest,
    data_service: ExternalDataService = Depends(get_initialized_data_service),
) -> ApiResponse[RiskScore]:
    """Analyze financial risk for a given stock.

    Performs comprehensive financial fraud detection including:
    - Beneish M-Score for earnings manipulation
    - 存贷双高
    - Goodwill ratio analysis
    - Profit vs cash flow divergence detection

    Args:
        request: Risk analysis request with ticker
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
        current_year = request.year if hasattr(request, 'year') and request.year else None
        current_report = await data_service.get_financial_report(ticker, current_year)

        # Get previous year's report for YoY comparison
        previous_year = current_report['fiscal_year'] - 1 if current_year is None else current_year - 1
        previous_report = await data_service.get_financial_report(ticker, previous_year)

        # Analyze risk
        analyzer = RiskAnalyzer()
        risk_score = analyzer.analyze(current_report, previous_report)

        # TODO: Save to database
        # await risk_repo.create(risk_score)

        return ApiResponse(success=True, data=risk_score)

    except DataValidationError as e:
        return ApiResponse(success=False, error=str(e))
    except ExternalAPIError as e:
        return ApiResponse(success=False, error=f"Failed to fetch financial data: {e}")
    except Exception as e:
        return ApiResponse(success=False, error=f"Internal server error: {e}")
