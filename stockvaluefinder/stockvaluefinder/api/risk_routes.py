"""Risk analysis API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.base import get_db
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
    db: AsyncSession = Depends(get_db),
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

        # TODO: In production, fetch actual financial data from:
        # 1. Database cache
        # 2. External API (Tushare/AKShare)
        # For now, return mock data for testing

        # Mock current financial data (for testing)
        current_report = _mock_current_financial_report(ticker)

        # Mock previous year data (for YoY comparison)
        previous_report = _mock_previous_financial_report(ticker)

        # Analyze risk
        analyzer = RiskAnalyzer()
        risk_score = analyzer.analyze(current_report, previous_report)

        # TODO: Save to database
        # await risk_repo.create(risk_score)

        # Use mode='json' to properly serialize Decimal to float
        return ApiResponse(success=True, data=risk_score.model_dump(mode='json'))

    except DataValidationError as e:
        return ApiResponse(success=False, error=str(e))
    except ExternalAPIError as e:
        return ApiResponse(success=False, error=f"Failed to fetch financial data: {e}")
    except Exception as e:
        return ApiResponse(success=False, error=f"Internal server error: {e}")


def _mock_current_financial_report(ticker: str) -> dict[str, Any]:
    """Generate mock current financial report for testing.

    In production, this would fetch from:
    1. Database cache
    2. Tushare/AKShare API
    3. PDF parsing (for new reports)
    """
    return {
        "ticker": ticker,
        "report_id": "00000000-0000-0000-0000-000000000001",
        "period": "2023-12-31",
        "report_type": "ANNUAL",
        "fiscal_year": 2023,
        "fiscal_quarter": None,
        "revenue": "10000000000",  # 10B
        "net_income": "2000000000",  # 2B
        "operating_cash_flow": "2500000000",  # 2.5B
        "gross_margin": 45.0,
        "assets_total": "50000000000",  # 50B
        "liabilities_total": "20000000000",  # 20B
        "equity_total": "30000000000",  # 30B
        "accounts_receivable": "500000000",  # 500M
        "inventory": "1000000000",  # 1B
        "fixed_assets": "15000000000",  # 15B
        "goodwill": "2000000000",  # 2B
        "cash_and_equivalents": "8000000000",  # 8B
        "interest_bearing_debt": "5000000000",  # 5B
        "report_source": "Tushare",
        # Pre-calculated indices for M-Score
        "days_sales_receivables_index": 1.1,
        "gross_margin_index": 0.95,
        "asset_quality_index": 1.05,
        "sales_growth_index": 1.15,
        "depreciation_index": 1.0,
        "sga_expense_index": 1.1,
        "leverage_index": 1.0,
        "total_accruals_to_assets": 0.02,
    }


def _mock_previous_financial_report(ticker: str) -> dict[str, Any]:
    """Generate mock previous year financial report for YoY comparison."""
    return {
        "ticker": ticker,
        "period": "2022-12-31",
        "net_income": "1800000000",  # 1.8B
        "operating_cash_flow": "2200000000",  # 2.2B
        "cash_and_equivalents": "6000000000",  # 6B
        "interest_bearing_debt": "4000000000",  # 4B
    }
