"""Risk analysis service - pure functions for financial fraud detection."""

from decimal import Decimal
from typing import Any

from stockvaluefinder.models.enums import RiskLevel
from stockvaluefinder.models.risk import MScoreData, RiskScore


def calculate_beneish_m_score(
    current_financials: dict[str, Any],
    previous_financials: dict[str, Any],
) -> dict[str, float]:
    """Calculate Beneish M-Score for earnings manipulation detection.

    M-Score = -4.84 + 0.92*DSRI + 0.528*GMI + 0.404*AQI
              + 0.892*SGI + 0.115*DEPI - 0.172*SGAI + 4.679*TATA - 0.327*LVGI

    Args:
        current_financials: Current year financial data with:
            - days_sales_receivables_index (DSRI)
            - gross_margin_index (GMI)
            - asset_quality_index (AQI)
            - sales_growth_index (SGI)
            - depreciation_index (DEPI)
            - sga_expense_index (SGAI)
            - leverage_index (LVGI)
            - total_accruals_to_assets (TATA)
        previous_financials: Previous year financial data (for index calculations)

    Returns:
        Dictionary with M-Score and all 8 component indices:
            - m_score: Overall M-Score
            - dsri: Days' Sales in Receivables Index
            - gmi: Gross Margin Index
            - aqi: Asset Quality Index
            - sgi: Sales Growth Index
            - depi: Depreciation Index
            - sgai: SG&A Expense Index
            - lvgi: Leverage Index
            - tata: Total Accruals to Total Assets

    Reference:
        Beneish, M. D. (1999). The detection of earnings manipulation.
        Financial Analysts Journal, 55(5), 24-36.
    """
    # Extract indices (if pre-calculated)
    dsri = float(current_financials.get("days_sales_receivables_index", 1.0))
    gmi = float(current_financials.get("gross_margin_index", 1.0))
    aqi = float(current_financials.get("asset_quality_index", 1.0))
    sgi = float(current_financials.get("sales_growth_index", 1.0))
    depi = float(current_financials.get("depreciation_index", 1.0))
    sgai = float(current_financials.get("sga_expense_index", 1.0))
    lvgi = float(current_financials.get("leverage_index", 1.0))
    tata = float(current_financials.get("total_accruals_to_assets", 0.0))

    # Calculate M-Score using Beneish formula
    m_score = (
        -4.84
        + 0.92 * dsri
        + 0.528 * gmi
        + 0.404 * aqi
        + 0.892 * sgi
        + 0.115 * depi
        - 0.172 * sgai
        + 4.679 * tata
        - 0.327 * lvgi
    )

    return {
        "m_score": round(m_score, 4),
        "dsri": round(dsri, 4),
        "gmi": round(gmi, 4),
        "aqi": round(aqi, 4),
        "sgi": round(sgi, 4),
        "depi": round(depi, 4),
        "sgai": round(sgai, 4),
        "lvgi": round(lvgi, 4),
        "tata": round(tata, 4),
    }


def detect_存贷双高(
    current_financials: dict[str, Any],
    previous_financials: dict[str, Any],
) -> dict[str, Any]:
    """Detect 'high cash + high debt' anomaly (存贷双高).

    This is a red flag where a company has both large cash reserves
    AND high debt levels, which may indicate cash fabrication.

    Thresholds:
    - Cash and equivalents > 1 billion yuan
    - Interest-bearing debt > 1 billion yuan
    - YoY cash growth > 50%
    - YoY debt growth > 50%

    Args:
        current_financials: Current year financial data with:
            - cash_and_equivalents
            - interest_bearing_debt
            - total_assets
        previous_financials: Previous year financial data with:
            - cash_and_equivalents
            - interest_bearing_debt

    Returns:
        Dictionary with:
            - 存贷双高: Boolean flag indicating anomaly
            - cash_amount: Current cash amount
            - debt_amount: Current debt amount
            - cash_growth_rate: YoY cash growth rate
            - debt_growth_rate: YoY debt growth rate
    """
    from decimal import Decimal

    # Extract amounts
    current_cash = Decimal(str(current_financials["cash_and_equivalents"]))
    current_debt = Decimal(str(current_financials["interest_bearing_debt"]))
    previous_cash = Decimal(str(previous_financials["cash_and_equivalents"]))
    previous_debt = Decimal(str(previous_financials["interest_bearing_debt"]))

    # Calculate growth rates
    if previous_cash > 0:
        cash_growth = float((current_cash - previous_cash) / previous_cash)
    else:
        cash_growth = 1.0 if current_cash > 0 else 0.0

    if previous_debt > 0:
        debt_growth = float((current_debt - previous_debt) / previous_debt)
    else:
        debt_growth = 1.0 if current_debt > 0 else 0.0

    # Apply thresholds (1 billion yuan = 1,000,000,000)
    cash_high = current_cash > Decimal("1_000_000_000")
    debt_high = current_debt > Decimal("1_000_000_000")
    cash_growth_high = cash_growth > 0.5  # 50%
    debt_growth_high = debt_growth > 0.5  # 50%

    # Flag if both cash and debt are high with significant growth
    存贷双高_flag = cash_high and debt_high and (cash_growth_high or debt_growth_high)

    return {
        "存贷双高": 存贷双高_flag,
        "cash_amount": current_cash,
        "debt_amount": current_debt,
        "cash_growth_rate": round(cash_growth, 4),
        "debt_growth_rate": round(debt_growth, 4),
    }


def calculate_goodwill_ratio(
    goodwill: Decimal,
    equity: Decimal,
) -> dict[str, Any]:
    """Calculate goodwill ratio and check if excessive.

    Goodwill ratio > 30% is considered excessive and may indicate
    overpayment for acquisitions.

    Args:
        goodwill: Goodwill amount from balance sheet
        equity: Total equity from balance sheet

    Returns:
        Dictionary with:
            - ratio: Goodwill / Equity ratio (0-1)
            - excessive: Boolean flag if ratio > 30%
    """
    if equity > 0:
        ratio = float(goodwill / equity)
    else:
        ratio = 0.0

    excessive = ratio > 0.30  # 30%

    return {
        "ratio": round(ratio, 4),
        "excessive": excessive,
    }


def detect_profit_cash_divergence(
    current_profit: Decimal,
    previous_profit: Decimal,
    current_ocf: Decimal,
    previous_ocf: Decimal,
) -> dict[str, Any]:
    """Detect divergence between profit growth and operating cash flow.

    This is a red flag when net income grows but operating cash flow declines,
    which may indicate earnings manipulation through accounting tricks.

    Args:
        current_profit: Current year net income
        previous_profit: Previous year net income
        current_ocf: Current year operating cash flow
        previous_ocf: Previous year operating cash flow

    Returns:
        Dictionary with:
            - divergence: Boolean flag indicating divergence
            - profit_growth: YoY profit growth rate
            - ocf_growth: YoY OCF growth rate
    """
    # Calculate growth rates
    if previous_profit > 0:
        profit_growth = float((current_profit - previous_profit) / previous_profit)
    else:
        profit_growth = 1.0 if current_profit > 0 else 0.0

    if previous_ocf > 0:
        ocf_growth = float((current_ocf - previous_ocf) / previous_ocf)
    else:
        ocf_growth = 1.0 if current_ocf > 0 else 0.0

    # Divergence: profit grows but OCF declines
    divergence = profit_growth > 0 and ocf_growth < 0

    return {
        "divergence": divergence,
        "profit_growth": round(profit_growth, 4),
        "ocf_growth": round(ocf_growth, 4),
    }


def determine_risk_level(m_score: float, red_flags_count: int) -> RiskLevel:
    """Determine overall risk level based on M-Score and red flags.

    Risk thresholds:
    - M-Score >= -1.78: HIGH or CRITICAL
    - M-Score < -2.22: LOW
    - Otherwise: MEDIUM

    Adjust based on red flags count.

    Args:
        m_score: Beneish M-Score value
        red_flags_count: Number of red flags detected

    Returns:
        RiskLevel enum value
    """
    # Base risk from M-Score
    if m_score >= -1.78:
        base_risk = RiskLevel.HIGH
        # Upgrade to CRITICAL if multiple red flags
        if red_flags_count >= 3:
            base_risk = RiskLevel.CRITICAL
    elif m_score < -2.22:
        base_risk = RiskLevel.LOW
    else:
        base_risk = RiskLevel.MEDIUM

    # Adjust for red flags
    if red_flags_count >= 2 and base_risk == RiskLevel.LOW:
        base_risk = RiskLevel.MEDIUM
    elif red_flags_count >= 4 and base_risk == RiskLevel.MEDIUM:
        base_risk = RiskLevel.HIGH

    return base_risk


def analyze_financial_risk(
    current_report: dict[str, Any],
    previous_report: dict[str, Any] | None,
) -> RiskScore:
    """Perform comprehensive financial risk analysis.

    This is the main orchestrator that calculates all risk metrics
    and determines the overall risk level.

    Args:
        current_report: Current financial report data
        previous_report: Previous year financial report (for YoY comparisons)

    Returns:
        RiskScore object with complete risk assessment
    """
    from datetime import datetime
    from uuid import uuid4

    red_flags = []

    # Calculate Beneish M-Score
    m_score_result = calculate_beneish_m_score(current_report, previous_report or {})
    m_score = m_score_result["m_score"]

    # Check M-Score threshold
    if m_score >= -1.78:
        red_flags.append("Beneish M-Score indicates earnings manipulation risk")

    # Detect 存贷双高
    存贷双高_result = detect_存贷双高(current_report, previous_report or {})
    if 存贷双高_result["存贷双高"]:
        red_flags.append("存贷双高: High cash and high debt anomaly detected")

    # Calculate goodwill ratio
    goodwill_result = calculate_goodwill_ratio(
        Decimal(str(current_report.get("goodwill", 0))),
        Decimal(str(current_report.get("equity_total", 1))),
    )
    if goodwill_result["excessive"]:
        red_flags.append("Goodwill exceeds 30% of equity, potential overpayment risk")

    # Detect profit-cash divergence
    if previous_report:
        divergence_result = detect_profit_cash_divergence(
            Decimal(str(current_report.get("net_income", 0))),
            Decimal(str(previous_report.get("net_income", 0))),
            Decimal(str(current_report.get("operating_cash_flow", 0))),
            Decimal(str(previous_report.get("operating_cash_flow", 0))),
        )
        if divergence_result["divergence"]:
            red_flags.append("Net income grew but operating cash flow declined")

    # Determine risk level
    risk_level = determine_risk_level(m_score, len(red_flags))

    # Build MScoreData
    mscore_data = MScoreData(
        dsri=m_score_result["dsri"],
        gmi=m_score_result["gmi"],
        aqi=m_score_result["aqi"],
        sgi=m_score_result["sgi"],
        depi=m_score_result["depi"],
        sgai=m_score_result["sgai"],
        lvgi=m_score_result["lvgi"],
        tata=m_score_result["tata"],
    )

    return RiskScore(
        score_id=uuid4(),
        ticker=current_report["ticker"],
        report_id=current_report.get("report_id", uuid4()),
        risk_level=risk_level,
        calculated_at=datetime.utcnow(),
        m_score=m_score,
        mscore_data=mscore_data,
        存贷双高=存贷双高_result["存贷双高"],
        cash_amount=存贷双高_result["cash_amount"],
        debt_amount=存贷双高_result["debt_amount"],
        cash_growth_rate=存贷双高_result["cash_growth_rate"],
        debt_growth_rate=存贷双高_result["debt_growth_rate"],
        goodwill_ratio=goodwill_result["ratio"],
        goodwill_excessive=goodwill_result["excessive"],
        profit_cash_divergence=divergence_result.get("divergence", False),
        profit_growth=divergence_result.get("profit_growth", 0.0),
        ocf_growth=divergence_result.get("ocf_growth", 0.0),
        red_flags=red_flags,
    )


class RiskAnalyzer:
    """Service class for risk analysis (orchestrates pure functions)."""

    def __init__(self) -> None:
        """Initialize RiskAnalyzer service."""
        pass

    def analyze(
        self,
        current_report: dict[str, Any],
        previous_report: dict[str, Any] | None = None,
    ) -> RiskScore:
        """Analyze financial risk for a given stock.

        Args:
            current_report: Current financial report
            previous_report: Previous year report (optional)

        Returns:
            RiskScore with complete risk assessment
        """
        return analyze_financial_risk(current_report, previous_report)
