"""ROIC-WACC spread analysis service - pure functions for value creation measurement.

This module provides pure functions for calculating Return on Invested Capital (ROIC),
Weighted Average Cost of Capital (WACC) spread, and competitive moat trend detection.

Key formulas:
    - ROIC = NOPAT / Invested Capital
    - NOPAT (non-financial) = (Total Profit + Finance Expense) * (1 - Tax Rate)
    - NOPAT (financial) = Operating Profit * (1 - Tax Rate)
    - Invested Capital = Equity + Short Debt + Long Debt + Bonds - Treasury Stock
    - Spread = ROIC - WACC
    - Moat Trend = linear regression slope of 3-year spreads
"""

from typing import Any

from stockvaluefinder.config import roic_config
from stockvaluefinder.models.roic import MoatTrend, SpreadClassification
from stockvaluefinder.services.risk_service import _to_float


def is_financial_sector(industry: str) -> bool:
    """Check if a stock belongs to the financial sector based on industry name.

    Detects Chinese financial sector keywords: bank (银行), insurance (保险),
    securities (证券).

    Args:
        industry: Industry classification string (e.g., "银行II", "白酒II").

    Returns:
        True if the industry string contains any financial sector keyword.

    Examples:
        >>> is_financial_sector("银行II")
        True
        >>> is_financial_sector("白酒II")
        False
        >>> is_financial_sector("")
        False
    """
    if not industry:
        return False
    return any(keyword in industry for keyword in roic_config.FINANCIAL_SECTOR_KEYWORDS)


def calculate_nopat(
    profit_data: dict[str, Any],
    is_financial: bool,
) -> tuple[float | None, dict[str, Any]]:
    """Calculate Net Operating Profit After Tax (NOPAT).

    Uses dual formula based on sector (D-10):
    - Non-financial: NOPAT = (Total Profit + Finance Expense) * (1 - Tax Rate)
    - Financial: NOPAT = Operating Profit * (1 - Tax Rate)

    Args:
        profit_data: Dictionary with financial data fields:
            - TOTAL_PROFIT: Total profit before tax
            - FINANCE_EXPENSE: Interest expense (non-financial only)
            - INCOME_TAX: Income tax paid
            - OPERATE_PROFIT: Operating profit (financial only)
        is_financial: True if the stock is in the financial sector.

    Returns:
        Tuple of (NOPAT value, audit_trail dict) where audit_trail contains:
        - nopat: calculated NOPAT value
        - tax_rate: effective tax rate
        - formula: formula used
        - inputs: raw input values

    Examples:
        >>> nopat, audit = calculate_nopat({"TOTAL_PROFIT": 100, "FINANCE_EXPENSE": 10, "INCOME_TAX": 25}, False)
        >>> abs(nopat - 82.5) < 1e-6
        True
    """
    total_profit = _to_float(profit_data.get("TOTAL_PROFIT"), "TOTAL_PROFIT")
    finance_expense = _to_float(profit_data.get("FINANCE_EXPENSE"), "FINANCE_EXPENSE")
    income_tax = _to_float(profit_data.get("INCOME_TAX"), "INCOME_TAX")
    operate_profit = _to_float(profit_data.get("OPERATE_PROFIT"), "OPERATE_PROFIT")

    # Calculate effective tax rate
    tax_rate = income_tax / total_profit if total_profit != 0 else 0.0

    if is_financial:
        nopat = operate_profit * (1 - tax_rate)
        formula = "OPERATE_PROFIT * (1 - tax_rate)"
        inputs = {
            "OPERATE_PROFIT": operate_profit,
            "INCOME_TAX": income_tax,
            "TOTAL_PROFIT": total_profit,
        }
    else:
        nopat = (total_profit + finance_expense) * (1 - tax_rate)
        formula = "(TOTAL_PROFIT + FINANCE_EXPENSE) * (1 - tax_rate)"
        inputs = {
            "TOTAL_PROFIT": total_profit,
            "FINANCE_EXPENSE": finance_expense,
            "INCOME_TAX": income_tax,
        }

    audit_trail: dict[str, Any] = {
        "nopat": round(nopat, 6),
        "tax_rate": round(tax_rate, 6),
        "formula": formula,
        "inputs": inputs,
    }

    return round(nopat, 6), audit_trail


def calculate_invested_capital(
    balance_sheet: dict[str, Any],
) -> tuple[float | None, bool]:
    """Calculate total invested capital from balance sheet data.

    Formula: IC = Equity + Short Debt + Long Debt + Bonds - Treasury Stock
    Handles NaN/None normalization to 0.0 (D-11).
    Returns None with negative_invested_capital=True when IC <= 0 (D-08).

    Args:
        balance_sheet: Dictionary with balance sheet fields:
            - TOTAL_PARENT_EQUITY: Parent company equity
            - SHORT_LOAN: Short-term borrowings
            - LONG_LOAN: Long-term borrowings
            - BOND_PAYABLE: Bonds payable
            - TREASURY_SHARES: Treasury stock (deducted)

    Returns:
        Tuple of (invested capital value or None, negative_invested_capital flag).
        When IC <= 0, returns (None, True). Otherwise (IC value, False).

    Examples:
        >>> ic, flag = calculate_invested_capital({"TOTAL_PARENT_EQUITY": 500, "SHORT_LOAN": 100, "LONG_LOAN": 200, "BOND_PAYABLE": 50, "TREASURY_SHARES": 20})
        >>> abs(ic - 830) < 1e-6
        True
        >>> flag
        False
    """
    equity = _to_float(balance_sheet.get("TOTAL_PARENT_EQUITY"), "TOTAL_PARENT_EQUITY")
    short_debt = _to_float(balance_sheet.get("SHORT_LOAN"), "SHORT_LOAN")
    long_debt = _to_float(balance_sheet.get("LONG_LOAN"), "LONG_LOAN")
    bonds = _to_float(balance_sheet.get("BOND_PAYABLE"), "BOND_PAYABLE")
    treasury = _to_float(balance_sheet.get("TREASURY_SHARES"), "TREASURY_SHARES")

    ic = equity + short_debt + long_debt + bonds - treasury

    if ic <= 0:
        return None, True

    return round(ic, 6), False


def calculate_roic(
    nopat: float | None,
    invested_capital: float | None,
    negative_ic: bool,
) -> float | None:
    """Calculate Return on Invested Capital (ROIC).

    ROIC = NOPAT / Invested Capital

    Args:
        nopat: Net Operating Profit After Tax.
        invested_capital: Total invested capital.
        negative_ic: True if invested capital was negative (from calculate_invested_capital).

    Returns:
        ROIC as decimal, or None if IC <= 0, None, or NOPAT is None.

    Examples:
        >>> abs(calculate_roic(82.5, 830, False) - 0.099398) < 0.001
        True
        >>> calculate_roic(82.5, -100, True) is None
        True
        >>> calculate_roic(82.5, 0, False) is None
        True
    """
    if negative_ic:
        return None
    if invested_capital is None or invested_capital == 0:
        return None
    if nopat is None:
        return None
    return round(nopat / invested_capital, 6)


def calculate_roic_wacc_spread(
    roic: float | None,
    wacc: float,
) -> tuple[float | None, SpreadClassification]:
    """Calculate the ROIC-WACC spread and classify value creation.

    Spread = ROIC - WACC
    - Positive (>= 0): VALUE_CREATING
    - Negative (< 0): VALUE_DESTROYING
    - ROIC is None: INSUFFICIENT_DATA

    Args:
        roic: Return on Invested Capital, or None if unavailable.
        wacc: Weighted Average Cost of Capital.

    Returns:
        Tuple of (spread value or None, SpreadClassification enum).

    Examples:
        >>> spread, cls = calculate_roic_wacc_spread(0.12, 0.09)
        >>> abs(spread - 0.03) < 1e-10
        True
        >>> cls
        <SpreadClassification.VALUE_CREATING: 'Value Creating'>
    """
    if roic is None:
        return None, SpreadClassification.INSUFFICIENT_DATA

    spread = round(roic - wacc, 6)
    if spread >= 0:
        return spread, SpreadClassification.VALUE_CREATING
    else:
        return spread, SpreadClassification.VALUE_DESTROYING


def analyze_roic_trend(
    spreads: list[float | None],
    years: list[int],
) -> dict[str, Any]:
    """Analyze ROIC-WACC spread trend over multiple years using linear regression (D-06).

    Uses scipy.stats.linregress to compute the slope of the spread time series.
    Classification:
    - slope > MOAT_TREND_THRESHOLD (0.005): COMPETITIVE_ADVANTAGE
    - slope < -MOAT_TREND_THRESHOLD (-0.005): DETERIORATING
    - Otherwise: STABLE
    - Fewer than MIN_TREND_DATA_POINTS (3) valid points: INSUFFICIENT_DATA

    Args:
        spreads: List of ROIC-WACC spread values (may contain None for missing years).
        years: List of fiscal years corresponding to each spread.

    Returns:
        Dictionary with keys: trend (MoatTrend), slope, p_value, data_points.

    Examples:
        >>> result = analyze_roic_trend([0.01, 0.03, 0.05], [2021, 2022, 2023])
        >>> result["trend"]
        <MoatTrend.COMPETITIVE_ADVANTAGE: 'Competitive Advantage'>
    """
    # Filter out None values and NaN (None != None is False, but NaN check needed)
    valid: list[tuple[int, float]] = []
    for year, spread in zip(years, spreads):
        if spread is not None and spread == spread:  # NaN check: NaN != NaN
            valid.append((year, spread))

    if len(valid) < roic_config.MIN_TREND_DATA_POINTS:
        return {
            "trend": MoatTrend.INSUFFICIENT_DATA,
            "slope": None,
            "p_value": None,
            "data_points": len(valid),
        }

    # Use ordinal positions for x-axis (avoids year gaps affecting slope)
    x = list(range(len(valid)))
    y = [s for _, s in valid]

    # Import here to match project convention of lazy imports for heavy deps
    from scipy.stats import linregress

    regression_result = linregress(x, y)
    slope = regression_result.slope
    p_value = regression_result.pvalue

    if slope > roic_config.MOAT_TREND_THRESHOLD:
        trend = MoatTrend.COMPETITIVE_ADVANTAGE
    elif slope < -roic_config.MOAT_TREND_THRESHOLD:
        trend = MoatTrend.DETERIORATING
    else:
        trend = MoatTrend.STABLE

    return {
        "trend": trend,
        "slope": round(slope, 6),
        "p_value": round(p_value, 6),
        "data_points": len(valid),
    }
