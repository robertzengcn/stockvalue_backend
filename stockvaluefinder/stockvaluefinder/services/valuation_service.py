"""DCF valuation service - pure functions for intrinsic value calculation."""

from decimal import Decimal
from typing import Any
from uuid import UUID

from stockvaluefinder.models.enums import ValuationLevel
from stockvaluefinder.models.valuation import DCFParams, ValuationResult


def calculate_wacc(
    risk_free_rate: float,
    beta: float,
    market_risk_premium: float,
) -> float:
    """Calculate Weighted Average Cost of Capital (WACC).

    Using CAPM: WACC = Rf + β × ERP

    Args:
        risk_free_rate: Risk-free rate (e.g., 10-year treasury yield)
        beta: Stock beta (systematic risk)
        market_risk_premium: Equity risk premium

    Returns:
        WACC as decimal (e.g., 0.09 for 9%)

    Examples:
        >>> calculate_wacc(0.03, 1.0, 0.06)
        0.09
        >>> calculate_wacc(0.025, 1.2, 0.05)
        0.085
    """
    return risk_free_rate + (beta * market_risk_premium)


def project_fcf(
    base_fcf: float,
    growth_rate: float,
    year: int,
) -> float:
    """Project Free Cash Flow for a given year.

    FCF_t = base_FCF × (1 + g)^t

    Args:
        base_fcf: Base year free cash flow
        growth_rate: Annual growth rate (as decimal)
        year: Year number (0-indexed)

    Returns:
        Projected FCF for the year

    Examples:
        >>> project_fcf(100.0, 0.05, 0)
        100.0
        >>> project_fcf(100.0, 0.05, 5)
        127.62815625
    """
    return base_fcf * ((1 + growth_rate) ** year)


def calculate_present_value(
    fcf_stream: list[float],
    wacc: float,
) -> float:
    """Calculate present value of future cash flows.

    PV = Σ [FCF_t / (1 + WACC)^t]

    Args:
        fcf_stream: List of future cash flows
        wacc: Discount rate (WACC)

    Returns:
        Present value of cash flow stream

    Examples:
        >>> calculate_present_value([100.0, 100.0, 100.0], 0.10)
        248.6851991
    """
    pv = 0.0
    for t, fcf in enumerate(fcf_stream, start=1):
        pv += fcf / ((1 + wacc) ** t)
    return pv


def calculate_terminal_value(
    final_fcf: float,
    growth_rate: float,
    wacc: float,
) -> float:
    """Calculate terminal value using Gordon Growth Model.

    TV = FCF_final × (1 + g) / (WACC - g)

    Args:
        final_fcf: Final year projected FCF
        growth_rate: Terminal growth rate (perpetual)
        wacc: Discount rate (WACC)

    Returns:
        Terminal value

    Examples:
        >>> calculate_terminal_value(100.0, 0.02, 0.10)
        1275.0
    """
    return final_fcf * (1 + growth_rate) / (wacc - growth_rate)


def calculate_margin_of_safety(
    intrinsic_value: float,
    current_price: float,
) -> float:
    """Calculate margin of safety.

    MoS = (intrinsic_value - current_price) / current_price

    Args:
        intrinsic_value: Calculated intrinsic value
        current_price: Current market price

    Returns:
        Margin of safety as decimal (positive = undervalued, negative = overvalued)

    Examples:
        >>> calculate_margin_of_safety(150.0, 100.0)
        0.5
        >>> calculate_margin_of_safety(80.0, 100.0)
        -0.2
    """
    return (intrinsic_value - current_price) / current_price


def determine_valuation_level(
    margin_of_safety: float,
) -> ValuationLevel:
    """Determine valuation level based on margin of safety.

    Valuation thresholds:
    - UNDERVERLUED: MoS >= 30% (0.30)
    - FAIR_VALUE: -30% < MoS < 30%
    - OVERVALUED: MoS <= -30% (-0.30)

    Args:
        margin_of_safety: Calculated margin of safety

    Returns:
        ValuationLevel enum

    Examples:
        >>> determine_valuation_level(0.50)
        <ValuationLevel.UNDERVERLUED: 'UNDERVERLUED'>
        >>> determine_valuation_level(0.10)
        <ValuationLevel.FAIR_VALUE: 'FAIR_VALUE'>
        >>> determine_valuation_level(-0.50)
        <ValuationLevel.OVERVALUED: 'OVERVALUED'>
    """
    if margin_of_safety >= 0.30:  # 30%
        return ValuationLevel.UNDERVERLUED
    elif margin_of_safety > -0.30:  # -30%
        return ValuationLevel.FAIR_VALUE
    else:
        return ValuationLevel.OVERVALUED


def analyze_dcf_valuation(
    ticker: str,
    current_price: Decimal,
    base_fcf: float,
    shares_outstanding: float,
    dcf_params: DCFParams,
    valuation_id: UUID,
) -> ValuationResult:
    """Perform comprehensive DCF valuation analysis.

    This is the main orchestrator that:
    1. Calculates WACC
    2. Projects FCFs for stage 1 and stage 2
    3. Calculates present value of explicit forecast period
    4. Calculates terminal value
    5. Sums PVs and divides by shares outstanding
    6. Determines margin of safety and valuation level

    Args:
        ticker: Stock code
        current_price: Current market price per share
        base_fcf: Base year free cash flow (total, not per-share)
        shares_outstanding: Number of shares outstanding
        dcf_params: DCF calculation parameters
        valuation_id: Unique identifier for this valuation

    Returns:
        ValuationResult with complete DCF analysis and audit trail
    """
    from datetime import datetime

    # Initialize audit trail
    audit_trail: dict[str, Any] = {
        "params": dcf_params.model_dump(),
        "fcf_projections": [],
        "present_values": [],
    }

    # Step 1: Calculate WACC
    wacc = calculate_wacc(
        dcf_params.risk_free_rate,
        dcf_params.beta,
        dcf_params.market_risk_premium,
    )
    audit_trail["wacc"] = round(wacc, 4)

    # Step 2: Project FCFs for stage 1 (high growth)
    stage1_fcfs: list[float] = []
    for year in range(1, dcf_params.years_stage1 + 1):
        fcf = project_fcf(base_fcf, dcf_params.growth_rate_stage1, year)
        stage1_fcfs.append(fcf)
        audit_trail["fcf_projections"].append(
            {
                "stage": 1,
                "year": year,
                "growth_rate": dcf_params.growth_rate_stage1,
                "fcf": round(fcf, 2),
            }
        )

    # Step 3: Project FCFs for stage 2 (stable growth)
    stage2_fcfs: list[float] = []
    stage1_final_fcf = stage1_fcfs[-1] if stage1_fcfs else base_fcf
    for year in range(1, dcf_params.years_stage2 + 1):
        fcf = project_fcf(stage1_final_fcf, dcf_params.growth_rate_stage2, year)
        stage2_fcfs.append(fcf)
        audit_trail["fcf_projections"].append(
            {
                "stage": 2,
                "year": dcf_params.years_stage1 + year,
                "growth_rate": dcf_params.growth_rate_stage2,
                "fcf": round(fcf, 2),
            }
        )

    # Step 4: Calculate present values
    all_fcfs = stage1_fcfs + stage2_fcfs
    pv_explicit_period = calculate_present_value(all_fcfs, wacc)
    audit_trail["present_values"].append(
        {
            "type": "explicit_period",
            "pv": round(pv_explicit_period, 2),
        }
    )

    # Step 5: Calculate terminal value
    final_fcf = all_fcfs[-1] if all_fcfs else base_fcf
    terminal_value = calculate_terminal_value(
        final_fcf,
        dcf_params.terminal_growth,
        wacc,
    )
    pv_terminal = terminal_value / ((1 + wacc) ** len(all_fcfs))
    audit_trail["terminal_value"] = round(terminal_value, 2)
    audit_trail["present_values"].append(
        {
            "type": "terminal_value",
            "tv": round(terminal_value, 2),
            "pv_tv": round(pv_terminal, 2),
        }
    )

    # Step 6: Calculate intrinsic value per share
    total_pv = pv_explicit_period + pv_terminal
    intrinsic_value_per_share = total_pv / shares_outstanding
    audit_trail["intrinsic_value"] = {
        "total_pv": round(total_pv, 2),
        "shares_outstanding": shares_outstanding,
        "per_share": round(intrinsic_value_per_share, 2),
    }

    # Step 7: Calculate margin of safety
    margin_of_safety = calculate_margin_of_safety(
        intrinsic_value_per_share,
        float(current_price),
    )
    audit_trail["margin_of_safety"] = round(margin_of_safety, 4)

    # Step 8: Determine valuation level
    valuation_level = determine_valuation_level(margin_of_safety)

    return ValuationResult(
        ticker=ticker,
        current_price=current_price,
        intrinsic_value=Decimal(str(round(intrinsic_value_per_share, 2))),
        wacc=wacc,
        margin_of_safety=margin_of_safety,
        valuation_level=valuation_level,
        valuation_id=valuation_id,
        calculated_at=datetime.utcnow(),
        dcf_params=dcf_params,
        audit_trail=audit_trail,
    )


class DCFValuationService:
    """Service class for DCF valuation (orchestrates pure functions)."""

    def __init__(self) -> None:
        """Initialize DCFValuationService."""
        pass

    def analyze(
        self,
        ticker: str,
        current_price: Decimal,
        base_fcf: float,
        shares_outstanding: float,
        dcf_params: DCFParams,
        valuation_id: UUID,
    ) -> ValuationResult:
        """Analyze DCF valuation for a given stock.

        Args:
            ticker: Stock code
            current_price: Current market price per share
            base_fcf: Base year free cash flow (total)
            shares_outstanding: Number of shares outstanding
            dcf_params: DCF calculation parameters
            valuation_id: Unique identifier for this valuation

        Returns:
            ValuationResult with complete DCF analysis
        """
        return analyze_dcf_valuation(
            ticker=ticker,
            current_price=current_price,
            base_fcf=base_fcf,
            shares_outstanding=shares_outstanding,
            dcf_params=dcf_params,
            valuation_id=valuation_id,
        )
