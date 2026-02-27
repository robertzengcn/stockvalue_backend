"""DCF Valuation API endpoints."""

from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.base import get_db
from stockvaluefinder.external.rate_client import RateClient
from stockvaluefinder.models.api import ApiResponse
from stockvaluefinder.models.valuation import DCFParams, DCFValuationRequest, ValuationResult
from stockvaluefinder.services.valuation_service import DCFValuationService
from stockvaluefinder.utils.errors import DataValidationError, ExternalAPIError

router = APIRouter(prefix="/api/v1/analyze/dcf", tags=["valuation"])


@router.post("/", response_model=ApiResponse[ValuationResult])
async def analyze_dcf(
    request: DCFValuationRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ValuationResult]:
    """Analyze DCF valuation for a given stock.

    Performs Discounted Cash Flow analysis to calculate intrinsic value
    with two-stage growth model and Gordon Growth terminal value.

    Args:
        request: DCF valuation request with ticker and parameters
        db: Database session

    Returns:
        ApiResponse with ValuationResult data including full audit trail
    """
    try:
        # Normalize ticker
        ticker = request.ticker.upper()

        # TODO: In production, fetch actual data from:
        # 1. Database cache
        # 2. External API (Tushare/AKShare)
        # For now, return mock data for testing

        # Mock current price
        current_price = _mock_current_price(ticker)

        # Mock financial data
        base_fcf = _mock_base_fcf(ticker)
        shares_outstanding = _mock_shares_outstanding(ticker)

        # Get risk-free rate (use provided or fetch current)
        rate_client = RateClient()
        risk_free_rate = request.risk_free_rate if request.risk_free_rate is not None else await rate_client.get_10y_treasury_yield()

        # Use provided or default beta
        beta = request.beta if request.beta is not None else 1.0

        # Use provided or default market risk premium
        market_risk_premium = request.market_risk_premium if request.market_risk_premium is not None else 0.06

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

        # TODO: Save to database
        # await valuation_repo.create(valuation)

        return ApiResponse(success=True, data=valuation.model_dump())

    except DataValidationError as e:
        return ApiResponse(success=False, error=str(e))
    except ExternalAPIError as e:
        return ApiResponse(success=False, error=f"Failed to fetch market data: {e}")
    except Exception as e:
        return ApiResponse(success=False, error=f"Internal server error: {e}")


def _mock_current_price(ticker: str) -> Decimal:
    """Generate mock current price for testing."""
    mock_prices: dict[str, Decimal] = {
        "600519.SH": Decimal("1800.00"),
        "0700.HK": Decimal("300.00"),
        "000002.SZ": Decimal("10.50"),
    }
    return mock_prices.get(ticker, Decimal("100.00"))


def _mock_base_fcf(ticker: str) -> float:
    """Generate mock base FCF for testing (total, not per-share)."""
    # Mock FCF in millions (as float)
    mock_fcfs: dict[str, float] = {
        "600519.SH": 50000.0,  # 50B
        "0700.HK": 120000.0,  # 120B
        "000002.SZ": 8000.0,  # 8B
    }
    return mock_fcfs.get(ticker, 10000.0)  # Default 10B


def _mock_shares_outstanding(ticker: str) -> float:
    """Generate mock shares outstanding for testing."""
    # Mock shares in millions
    mock_shares: dict[str, float] = {
        "600519.SH": 12.56,  # ~1.256B shares
        "0700.HK": 9400.0,  # ~9.4B shares
        "000002.SZ": 9700.0,  # ~9.7B shares
    }
    return mock_shares.get(ticker, 5000.0)  # Default 5B shares
