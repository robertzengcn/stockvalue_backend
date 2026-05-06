"""Alpha Composite Score API endpoint.

Provides a single endpoint that aggregates all forward-looking analysis
dimensions (ROIC-WACC, Capital Allocation, Policy Resonance, Moat Trend)
into a composite Alpha score with transparent fixed weighting.

The endpoint calls three existing analysis route handlers directly (not
via HTTP self-call) for live computation, normalizes each component to
0-100, applies fixed weights (40/30/20/10), persists the result, and
returns the complete breakdown including input values, intermediate
calculations, and weight assignments.
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.api.capex_routes import analyze_capital_allocation
from stockvaluefinder.api.dependencies import get_initialized_data_service
from stockvaluefinder.api.policy_routes import analyze_resonance
from stockvaluefinder.api.roic_routes import analyze_roic
from stockvaluefinder.config import alpha_config
from stockvaluefinder.db.base import get_db
from stockvaluefinder.external.data_service import ExternalDataService
from stockvaluefinder.models.alpha import (
    AlphaAnalysisResult,
    AlphaComponentScores,
    AlphaRequest,
    AlphaScoreCreate,
)
from stockvaluefinder.models.api import ApiResponse
from stockvaluefinder.models.capital_allocation import CapitalAllocationRequest
from stockvaluefinder.models.policy import ResonanceRequest
from stockvaluefinder.models.roic import ROICAnalysisRequest
from stockvaluefinder.repositories.alpha_repo import AlphaScoreRepository
from stockvaluefinder.services.alpha_service import (
    calculate_alpha_score,
    classify_alpha_level,
    normalize_capex_score,
    normalize_moat_score,
    normalize_policy_score,
    normalize_roic_wacc_score,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analyze/alpha", tags=["alpha"])


@router.post("/", response_model=ApiResponse[AlphaAnalysisResult])
async def analyze_alpha(
    request: AlphaRequest,
    data_service: ExternalDataService = Depends(get_initialized_data_service),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[AlphaAnalysisResult]:
    """Compute composite Alpha score by orchestrating live component analyses.

    Calls ROIC, Capital Allocation, and Policy Resonance endpoints directly
    to fetch fresh component scores. Normalizes each dimension to 0-100,
    applies fixed weights (40/30/20/10), classifies the result, persists
    to the alpha_scores table, and returns the full breakdown.

    Args:
        request: AlphaRequest with ticker and optional year.
        data_service: Injected ExternalDataService instance.
        db: Injected AsyncSession for database operations.

    Returns:
        ApiResponse wrapping AlphaAnalysisResult with composite score,
        component breakdown, weights, and audit trail.
    """
    try:
        ticker = request.ticker.upper()

        # Determine fiscal year: use request.year if provided, else current year - 1
        today = datetime.now(timezone.utc)
        fiscal_year: int = request.year if request.year else today.year - 1

        # =================================================================
        # (1) Call ROIC endpoint (D-05, D-06)
        # =================================================================
        roic_req = ROICAnalysisRequest(ticker=ticker, year=request.year)
        roic_resp = await analyze_roic(
            request=roic_req,
            data_service=data_service,
            db=db,
        )
        if not roic_resp.success or roic_resp.data is None:
            return ApiResponse(
                success=False,
                error=f"ROIC analysis failed: {roic_resp.error or 'no data'}",
            )

        roic_data = roic_resp.data
        spread: float | None = roic_data.spread
        moat_trend_enum = (
            roic_data.moat_trend.trend if roic_data.moat_trend is not None else None
        )
        roic_fiscal_year: int = roic_data.fiscal_year

        # =================================================================
        # (2) Call CapEx endpoint (D-06)
        # =================================================================
        capex_req = CapitalAllocationRequest(ticker=ticker, year=request.year)
        capex_resp = await analyze_capital_allocation(
            request=capex_req,
            data_service=data_service,
            db=db,
        )
        if not capex_resp.success or capex_resp.data is None:
            return ApiResponse(
                success=False,
                error=f"Capital allocation analysis failed: "
                f"{capex_resp.error or 'no data'}",
            )

        capex_data = capex_resp.data
        overall_grade = capex_data.overall_grade
        capex_fiscal_year: int = capex_data.fiscal_year

        # =================================================================
        # (3) Call Policy Resonance endpoint (D-06)
        # =================================================================
        policy_req = ResonanceRequest(ticker=ticker)
        policy_resp = await analyze_resonance(
            request=policy_req,
            data_service=data_service,
            db=db,
        )
        if not policy_resp.success or policy_resp.data is None:
            return ApiResponse(
                success=False,
                error=f"Policy resonance analysis failed: "
                f"{policy_resp.error or 'no data'}",
            )

        policy_data = policy_resp.data
        resonance_score: float = policy_data.resonance_score
        dcf_adjustment = policy_data.dcf_adjustment

        # =================================================================
        # (4) Normalize all component scores
        # =================================================================
        roic_wacc_norm = normalize_roic_wacc_score(spread)
        capex_norm = normalize_capex_score(overall_grade)
        policy_norm = normalize_policy_score(resonance_score)
        moat_norm = normalize_moat_score(moat_trend_enum)

        # =================================================================
        # (5) Calculate composite Alpha score
        # =================================================================
        weights = (
            alpha_config.ROIC_WACC_WEIGHT,
            alpha_config.CAPITAL_ALLOCATION_WEIGHT,
            alpha_config.POLICY_WEIGHT,
            alpha_config.MOAT_WEIGHT,
        )
        alpha_score = calculate_alpha_score(
            roic_wacc_norm, capex_norm, policy_norm, moat_norm, weights
        )
        alpha_level = classify_alpha_level(alpha_score)

        # =================================================================
        # (6) Build component scores
        # =================================================================
        component_scores = AlphaComponentScores(
            roic_wacc_score=roic_wacc_norm,
            roic_wacc_raw=spread,
            capex_score=capex_norm,
            capex_raw_grade=overall_grade.value,
            policy_score=policy_norm,
            policy_raw_score=resonance_score,
            moat_score=moat_norm,
            moat_raw_trend=moat_trend_enum.value if moat_trend_enum else None,
        )

        # =================================================================
        # (7) Build audit trail
        # =================================================================
        audit_trail: dict[str, Any] = {
            "roic_fiscal_year": roic_fiscal_year,
            "capex_fiscal_year": capex_fiscal_year,
            "spread": spread,
            "moat_trend": moat_trend_enum.value if moat_trend_enum else None,
            "overall_grade": overall_grade.value,
            "resonance_score": resonance_score,
            "normalization": {
                "roic_wacc": "linear_clamp_pm10",
                "capex": "grade_map_ABCD_100_75_50_25",
                "policy": "pass_through",
                "moat": "tier_map_100_50_0",
            },
        }

        # =================================================================
        # (8) Build weights_used dict
        # =================================================================
        weights_used: dict[str, float] = {
            "roic_wacc": weights[0],
            "capex": weights[1],
            "policy": weights[2],
            "moat": weights[3],
        }

        # =================================================================
        # (9) Build DCF adjustment summary
        # =================================================================
        dcf_summary: dict[str, Any] | None = None
        if dcf_adjustment is not None:
            dcf_summary = {
                "tier": dcf_adjustment.tier.value,
                "adjustment_pct": dcf_adjustment.adjustment_pct,
                "adjusted_terminal_growth": dcf_adjustment.adjusted_terminal_growth,
                "original_terminal_growth": dcf_adjustment.original_terminal_growth,
            }

        # =================================================================
        # (10) Build AlphaAnalysisResult
        # =================================================================
        result = AlphaAnalysisResult(
            ticker=ticker,
            fiscal_year=fiscal_year,
            component_scores=component_scores,
            alpha_score=alpha_score,
            alpha_level=alpha_level,
            weights_used=weights_used,
            dcf_adjustment_summary=dcf_summary,
            audit_trail=audit_trail,
            calculated_at=datetime.now(timezone.utc),
        )

        # =================================================================
        # (11) Persist to database (non-blocking)
        # =================================================================
        try:
            alpha_repo = AlphaScoreRepository(db)
            create_data = AlphaScoreCreate(
                analysis_id=uuid4(),
                ticker=ticker,
                fiscal_year=fiscal_year,
                roic_wacc_score=roic_wacc_norm,
                roic_wacc_raw=spread,
                capex_score=capex_norm,
                capex_raw_grade=overall_grade.value,
                policy_score=policy_norm,
                policy_raw_score=resonance_score,
                moat_score=moat_norm,
                moat_raw_trend=moat_trend_enum.value if moat_trend_enum else None,
                alpha_score=alpha_score,
                weights_used=weights_used,
                dcf_adjustment_summary=dcf_summary,
                audit_trail=audit_trail,
            )
            await alpha_repo.upsert_by_ticker_year(create_data)
            await db.commit()
            logger.info("Successfully saved Alpha analysis for %s to database", ticker)
        except Exception as db_error:
            await db.rollback()
            logger.error("Failed to save Alpha analysis for %s: %s", ticker, db_error)

        return ApiResponse(success=True, data=result)

    except Exception:
        logger.exception("Unexpected error in Alpha analysis for %s", request.ticker)
        return ApiResponse(
            success=False,
            error="An internal error occurred. Please try again later.",
        )
