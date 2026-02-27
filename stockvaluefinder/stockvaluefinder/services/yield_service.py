"""Yield gap service - pure functions for dividend analysis."""

from decimal import Decimal
from uuid import UUID

from stockvaluefinder.models.enums import Market, YieldRecommendation
from stockvaluefinder.models.yield_gap import YieldGap


def calculate_net_dividend_yield(
    gross_yield: float,
    market: Market,
) -> float:
    """Calculate net dividend yield after tax.

    Args:
        gross_yield: Gross dividend yield (as decimal, e.g., 0.05 for 5%)
        market: Market (A_SHARE or HK_SHARE)

    Returns:
        Net dividend yield after tax:
        - A-shares: 0% tax (gross_yield)
        - HK Stock Connect: 20% tax (gross_yield * 0.80)

    Examples:
        >>> calculate_net_dividend_yield(0.05, Market.A_SHARE)
        0.05
        >>> calculate_net_dividend_yield(0.05, Market.HK_SHARE)
        0.04
    """
    if market == Market.HK_SHARE:
        # HK Stock Connect: 20% withholding tax
        return gross_yield * 0.80
    else:
        # A-shares: 0% tax
        return gross_yield


def calculate_yield_gap(
    net_yield: float,
    risk_free_bond_rate: float,
    risk_free_deposit_rate: float,
) -> float:
    """Calculate yield gap between dividend yield and risk-free rates.

    Yield gap = net_dividend_yield - max(risk_free_bond, risk_free_deposit)

    Args:
        net_yield: Net dividend yield after tax
        risk_free_bond_rate: 10-year treasury bond rate
        risk_free_deposit_rate: 3-year large deposit rate

    Returns:
        Yield gap (can be negative if risk-free rates are higher)

    Examples:
        >>> calculate_yield_gap(0.05, 0.03, 0.025)
        0.025
        >>> calculate_yield_gap(0.02, 0.03, 0.04)
        -0.02
    """
    return net_yield - max(risk_free_bond_rate, risk_free_deposit_rate)


def determine_yield_recommendation(
    yield_gap: float,
) -> YieldRecommendation:
    """Determine investment recommendation based on yield gap.

    Recommendation thresholds:
    - ATTRACTIVE: yield_gap > 2%
    - NEUTRAL: -1% <= yield_gap <= 2%
    - UNATTRACTIVE: yield_gap < -1%

    Args:
        yield_gap: Calculated yield gap

    Returns:
        YieldRecommendation enum (ATTRACTIVE, NEUTRAL, or UNATTRACTIVE)

    Examples:
        >>> determine_yield_recommendation(0.025)
        <YieldRecommendation.ATTRACTIVE: 'ATTRACTIVE'>
        >>> determine_yield_recommendation(0.01)
        <YieldRecommendation.NEUTRAL: 'NEUTRAL'>
        >>> determine_yield_recommendation(-0.02)
        <YieldRecommendation.UNATTRACTIVE: 'UNATTRACTIVE'>
    """
    if yield_gap > 0.02:  # 2%
        return YieldRecommendation.ATTRACTIVE
    elif yield_gap >= -0.01:  # -1%
        return YieldRecommendation.NEUTRAL
    else:
        return YieldRecommendation.UNATTRACTIVE


def analyze_yield_gap(
    ticker: str,
    cost_basis: Decimal,
    current_price: Decimal,
    gross_dividend_yield: float,
    risk_free_bond_rate: float,
    risk_free_deposit_rate: float,
    market: Market,
    analysis_id: UUID,
) -> YieldGap:
    """Perform comprehensive yield gap analysis.

    This is the main orchestrator that calculates all yield metrics
    and determines the investment recommendation.

    Args:
        ticker: Stock code
        cost_basis: Purchase price per share
        current_price: Current market price per share
        gross_dividend_yield: Gross dividend yield (before tax)
        risk_free_bond_rate: 10-year treasury bond rate
        risk_free_deposit_rate: 3-year large deposit rate
        market: Market (A_SHARE or HK_SHARE)
        analysis_id: Unique identifier for this analysis

    Returns:
        YieldGap object with complete yield analysis
    """
    from datetime import datetime

    # Calculate net dividend yield (apply tax if HK)
    net_yield = calculate_net_dividend_yield(gross_dividend_yield, market)

    # Calculate yield gap
    yield_gap = calculate_yield_gap(
        net_yield, risk_free_bond_rate, risk_free_deposit_rate
    )

    # Determine recommendation
    recommendation = determine_yield_recommendation(yield_gap)

    return YieldGap(
        ticker=ticker,
        cost_basis=cost_basis,
        current_price=current_price,
        gross_dividend_yield=gross_dividend_yield,
        net_dividend_yield=net_yield,
        risk_free_bond_rate=risk_free_bond_rate,
        risk_free_deposit_rate=risk_free_deposit_rate,
        yield_gap=yield_gap,
        recommendation=recommendation,
        market=market,
        analysis_id=analysis_id,
        calculated_at=datetime.utcnow(),
    )


class YieldAnalyzer:
    """Service class for yield gap analysis (orchestrates pure functions)."""

    def __init__(self) -> None:
        """Initialize YieldAnalyzer service."""
        pass

    def analyze(
        self,
        ticker: str,
        cost_basis: Decimal,
        current_price: Decimal,
        gross_dividend_yield: float,
        risk_free_bond_rate: float,
        risk_free_deposit_rate: float,
        market: Market,
        analysis_id: UUID,
    ) -> YieldGap:
        """Analyze yield gap for a given stock.

        Args:
            ticker: Stock code
            cost_basis: Purchase price per share
            current_price: Current market price per share
            gross_dividend_yield: Gross dividend yield (before tax)
            risk_free_bond_rate: 10-year treasury bond rate
            risk_free_deposit_rate: 3-year large deposit rate
            market: Market (A_SHARE or HK_SHARE)
            analysis_id: Unique identifier for this analysis

        Returns:
            YieldGap with complete yield analysis
        """
        return analyze_yield_gap(
            ticker=ticker,
            cost_basis=cost_basis,
            current_price=current_price,
            gross_dividend_yield=gross_dividend_yield,
            risk_free_bond_rate=risk_free_bond_rate,
            risk_free_deposit_rate=risk_free_deposit_rate,
            market=market,
            analysis_id=analysis_id,
        )
