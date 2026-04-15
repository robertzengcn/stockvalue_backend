"""Risk analysis service - pure functions for financial fraud detection."""

from decimal import Decimal
from typing import Any

from stockvaluefinder.models.enums import RiskLevel
from stockvaluefinder.models.risk import (
    FScoreData,
    IndexAuditDetail,
    MScoreData,
    RiskScore,
)
from stockvaluefinder.utils.errors import DataValidationError


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


# Required M-Score fields that must exist in both current and previous reports
_MSCORE_REQUIRED_FIELDS = [
    "revenue",
    "net_income",
    "operating_cash_flow",
    "accounts_receivable",
    "cost_of_goods",
    "total_current_assets",
    "total_assets",
    "ppe",
    "sga_expense",
    "total_liabilities",
]


def _to_float(value: Any, field_name: str = "") -> float:
    """Convert a value to float, treating nan/None/empty as 0.0."""
    if value is None:
        return 0.0
    try:
        result = float(value)
        if result != result:  # NaN check
            return 0.0
        return result
    except (ValueError, TypeError):
        return 0.0


def calculate_mscore_indices(
    current_report: dict[str, Any],
    previous_report: dict[str, Any],
    source_name: str = "unknown",
) -> dict[str, Any]:
    """Calculate all 8 Beneish M-Score component indices from two-year data.

    Each index is computed as a year-over-year ratio from standardized
    financial data. Returns a dictionary with index values, audit trail,
    and any non-calculable indices.

    Args:
        current_report: Current year standardized financial data (from data_service)
        previous_report: Previous year standardized financial data
        source_name: Data source name for audit trail (e.g., "AKShare")

    Returns:
        Dictionary with:
            - dsri, gmi, aqi, sgi, depi, sgai, lvgi, tata: float values
            - non_calculable: list[str] of index names that could not be calculated
            - audit_trail: dict[str, IndexAuditDetail] with per-index details
            - red_flags: list[str] of warnings for non-calculable indices

    Raises:
        DataValidationError: If required fields are missing from either report

    Reference:
        Beneish, M. D. (1999). The detection of earnings manipulation.
        Financial Analysts Journal, 55(5), 24-36.
    """
    # Validate required fields exist (D-08: strict mode)
    missing_current = [
        f
        for f in _MSCORE_REQUIRED_FIELDS
        if f not in current_report or current_report[f] is None
    ]
    # Also check assets_total as alias for total_assets
    if "total_assets" in missing_current and "assets_total" in current_report:
        missing_current.remove("total_assets")

    missing_previous = [
        f
        for f in _MSCORE_REQUIRED_FIELDS
        if f not in previous_report or previous_report[f] is None
    ]
    if "total_assets" in missing_previous and "assets_total" in previous_report:
        missing_previous.remove("total_assets")

    if missing_current:
        raise DataValidationError(
            f"Missing required M-Score fields in current report: {', '.join(missing_current)}"
        )
    if missing_previous:
        raise DataValidationError(
            f"Missing required M-Score fields in previous report: {', '.join(missing_previous)}"
        )

    # Helper to resolve total_assets / assets_total naming
    def _get_assets(report: dict[str, Any]) -> float:
        return _to_float(report.get("total_assets", report.get("assets_total", 0)))

    # Extract values with nan-safe conversion
    curr_ar = _to_float(current_report["accounts_receivable"])
    curr_rev = _to_float(current_report["revenue"])
    prev_ar = _to_float(previous_report["accounts_receivable"])
    prev_rev = _to_float(previous_report["revenue"])

    curr_cogs = _to_float(current_report["cost_of_goods"])
    prev_cogs = _to_float(previous_report["cost_of_goods"])

    curr_ca = _to_float(current_report["total_current_assets"])
    curr_ppe = _to_float(current_report["ppe"])
    curr_ta = _get_assets(current_report)
    prev_ca = _to_float(previous_report["total_current_assets"])
    prev_ppe = _to_float(previous_report["ppe"])
    prev_ta = _get_assets(previous_report)

    curr_sga = _to_float(current_report["sga_expense"])
    prev_sga = _to_float(previous_report["sga_expense"])

    curr_tl = _to_float(current_report["total_liabilities"])
    prev_tl = _to_float(previous_report["total_liabilities"])

    curr_ni = _to_float(current_report["net_income"])
    curr_ocf = _to_float(current_report["operating_cash_flow"])

    non_calculable: list[str] = []
    red_flags: list[str] = []
    audit_trail: dict[str, IndexAuditDetail] = {}

    def _safe_ratio(
        num: float, denom: float, index_name: str
    ) -> tuple[float | None, float, float]:
        """Return (ratio, numerator, denominator) or (None, num, denom) if denom is 0."""
        if denom == 0:
            non_calculable.append(index_name)
            red_flags.append(f"{index_name}: denominator is zero, index not calculable")
            return None, num, denom
        return num / denom, num, denom

    # DSRI: Days' Sales Receivables Index
    dsri_ratio = (curr_ar / curr_rev) if curr_rev != 0 else float("inf")
    prev_dsri_ratio = (prev_ar / prev_rev) if prev_rev != 0 else float("inf")
    dsri_raw, dsri_num, dsri_den = _safe_ratio(dsri_ratio, prev_dsri_ratio, "DSRI")
    dsri = dsri_raw if dsri_raw is not None else 1.0
    audit_trail["dsri"] = IndexAuditDetail(
        value=dsri,
        numerator=dsri_num,
        denominator=dsri_den,
        source_fields={
            "accounts_receivable": f"ACCOUNTS_RECE ({source_name})",
            "revenue": f"TOTAL_OPERATE_INCOME ({source_name})",
        },
        non_calculable=dsri_raw is None,
        reason="denominator is zero" if dsri_raw is None else None,
    )

    # GMI: Gross Margin Index
    gm_curr = (curr_rev - curr_cogs) / curr_rev if curr_rev != 0 else 0.0
    gm_prev = (prev_rev - prev_cogs) / prev_rev if prev_rev != 0 else 0.0
    gmi_raw, gmi_num, gmi_den = _safe_ratio(gm_prev, gm_curr, "GMI")
    gmi = gmi_raw if gmi_raw is not None else 1.0
    audit_trail["gmi"] = IndexAuditDetail(
        value=gmi,
        numerator=gmi_num,
        denominator=gmi_den,
        source_fields={
            "revenue": f"TOTAL_OPERATE_INCOME ({source_name})",
            "cost_of_goods": f"OPERATE_COST ({source_name})",
        },
        non_calculable=gmi_raw is None,
        reason="denominator is zero" if gmi_raw is None else None,
    )

    # AQI: Asset Quality Index
    aq_curr = 1 - (curr_ca - curr_ppe) / curr_ta if curr_ta != 0 else 0.0
    aq_prev = 1 - (prev_ca - prev_ppe) / prev_ta if prev_ta != 0 else 0.0
    aqi_raw, aqi_num, aqi_den = _safe_ratio(aq_curr, aq_prev, "AQI")
    aqi = aqi_raw if aqi_raw is not None else 1.0
    audit_trail["aqi"] = IndexAuditDetail(
        value=aqi,
        numerator=aqi_num,
        denominator=aqi_den,
        source_fields={
            "total_current_assets": f"TOTAL_CURRENT_ASSETS ({source_name})",
            "ppe": f"FIXED_ASSET ({source_name})",
            "total_assets": f"TOTAL_ASSETS ({source_name})",
        },
        non_calculable=aqi_raw is None,
        reason="denominator is zero" if aqi_raw is None else None,
    )

    # SGI: Sales Growth Index
    sgi_raw, sgi_num, sgi_den = _safe_ratio(curr_rev, prev_rev, "SGI")
    sgi = sgi_raw if sgi_raw is not None else 1.0
    audit_trail["sgi"] = IndexAuditDetail(
        value=sgi,
        numerator=sgi_num,
        denominator=sgi_den,
        source_fields={
            "revenue": f"TOTAL_OPERATE_INCOME ({source_name})",
        },
        non_calculable=sgi_raw is None,
        reason="denominator is zero" if sgi_raw is None else None,
    )

    # DEPI: Depreciation Index = 1.0 (D-05 MVP simplification)
    depi = 1.0
    audit_trail["depi"] = IndexAuditDetail(
        value=depi,
        numerator=0.0,
        denominator=0.0,
        source_fields={
            "note": "MVP simplification per D-05, AKShare lacks direct depreciation field"
        },
        non_calculable=False,
        reason="MVP: hardcoded to 1.0 (depreciation data unavailable)",
    )

    # SGAI: SGA Expense Index
    sga_ratio_curr = curr_sga / curr_rev if curr_rev != 0 else 0.0
    sga_ratio_prev = prev_sga / prev_rev if prev_rev != 0 else 0.0
    sgai_raw, sgai_num, sgai_den = _safe_ratio(sga_ratio_curr, sga_ratio_prev, "SGAI")
    sgai = sgai_raw if sgai_raw is not None else 1.0
    audit_trail["sgai"] = IndexAuditDetail(
        value=sgai,
        numerator=sgai_num,
        denominator=sgai_den,
        source_fields={
            "sga_expense": f"TOTAL_OPERATE_COST ({source_name})",
            "revenue": f"TOTAL_OPERATE_INCOME ({source_name})",
        },
        non_calculable=sgai_raw is None,
        reason="denominator is zero" if sgai_raw is None else None,
    )

    # LVGI: Leverage Index (uses total_liabilities / total_assets per research finding)
    lev_curr = curr_tl / curr_ta if curr_ta != 0 else 0.0
    lev_prev = prev_tl / prev_ta if prev_ta != 0 else 0.0
    lvgi_raw, lvgi_num, lvgi_den = _safe_ratio(lev_curr, lev_prev, "LVGI")
    lvgi = lvgi_raw if lvgi_raw is not None else 1.0
    audit_trail["lvgi"] = IndexAuditDetail(
        value=lvgi,
        numerator=lvgi_num,
        denominator=lvgi_den,
        source_fields={
            "total_liabilities": f"TOTAL_LIABILITIES ({source_name})",
            "total_assets": f"TOTAL_ASSETS ({source_name})",
        },
        non_calculable=lvgi_raw is None,
        reason="denominator is zero" if lvgi_raw is None else None,
    )

    # TATA: Total Accruals to Total Assets (D-06 standard formula)
    tata = (curr_ni - curr_ocf) / curr_ta if curr_ta != 0 else 0.0
    audit_trail["tata"] = IndexAuditDetail(
        value=tata,
        numerator=curr_ni - curr_ocf,
        denominator=curr_ta,
        source_fields={
            "net_income": f"NETPROFIT ({source_name})",
            "operating_cash_flow": f"NETCASH_OPERATE ({source_name})",
            "total_assets": f"TOTAL_ASSETS ({source_name})",
        },
    )

    return {
        "dsri": round(dsri, 4),
        "gmi": round(gmi, 4),
        "aqi": round(aqi, 4),
        "sgi": round(sgi, 4),
        "depi": round(depi, 4),
        "sgai": round(sgai, 4),
        "lvgi": round(lvgi, 4),
        "tata": round(tata, 4),
        "non_calculable": non_calculable,
        "audit_trail": audit_trail,
        "red_flags": red_flags,
    }


def calculate_piotroski_f_score(
    current_financials: dict[str, Any],
    previous_financials: dict[str, Any],
) -> dict[str, Any]:
    """Calculate Piotroski F-Score (0-9) from two-year financial data."""

    def _to_decimal(value: Any, default: str = "0") -> Decimal:
        if value is None:
            return Decimal(default)
        return Decimal(str(value))

    def _ratio(numerator: Decimal, denominator: Decimal) -> float:
        if denominator <= 0:
            return 0.0
        return float(numerator / denominator)

    current_assets = _to_decimal(current_financials.get("assets_total"))
    previous_assets = _to_decimal(previous_financials.get("assets_total"))

    current_net_income = _to_decimal(current_financials.get("net_income"))
    previous_net_income = _to_decimal(previous_financials.get("net_income"))
    current_cfo = _to_decimal(current_financials.get("operating_cash_flow"))

    current_roa = _ratio(current_net_income, current_assets)
    previous_roa = _ratio(previous_net_income, previous_assets)
    current_cfo_ratio = _ratio(current_cfo, current_assets)

    has_current_debt = (
        "long_term_debt" in current_financials
        or "interest_bearing_debt" in current_financials
    )
    has_previous_debt = (
        "long_term_debt" in previous_financials
        or "interest_bearing_debt" in previous_financials
    )
    current_debt = _to_decimal(
        current_financials.get(
            "long_term_debt", current_financials.get("interest_bearing_debt")
        )
    )
    previous_debt = _to_decimal(
        previous_financials.get(
            "long_term_debt", previous_financials.get("interest_bearing_debt")
        )
    )
    current_leverage = _ratio(current_debt, current_assets)
    previous_leverage = _ratio(previous_debt, previous_assets)

    current_liabilities = _to_decimal(current_financials.get("liabilities_total"))
    previous_liabilities = _to_decimal(previous_financials.get("liabilities_total"))
    current_liquidity = _ratio(
        _to_decimal(current_financials.get("cash_and_equivalents")),
        current_liabilities,
    )
    previous_liquidity = _ratio(
        _to_decimal(previous_financials.get("cash_and_equivalents")),
        previous_liabilities,
    )

    current_shares = _to_decimal(current_financials.get("shares_outstanding"), "0")
    previous_shares = _to_decimal(previous_financials.get("shares_outstanding"), "0")

    current_margin = float(current_financials.get("gross_margin", 0.0))
    previous_margin = float(previous_financials.get("gross_margin", 0.0))

    current_turnover = _ratio(
        _to_decimal(current_financials.get("revenue")),
        current_assets,
    )
    previous_turnover = _ratio(
        _to_decimal(previous_financials.get("revenue")),
        previous_assets,
    )

    improving_roa = (
        "net_income" in previous_financials
        and "assets_total" in previous_financials
        and previous_assets > 0
        and current_roa > previous_roa
    )
    lower_leverage = (
        "assets_total" in previous_financials
        and previous_assets > 0
        and has_current_debt
        and has_previous_debt
        and current_leverage < previous_leverage
    )
    higher_liquidity = (
        "cash_and_equivalents" in current_financials
        and "liabilities_total" in current_financials
        and "cash_and_equivalents" in previous_financials
        and "liabilities_total" in previous_financials
        and current_liabilities > 0
        and previous_liabilities > 0
        and current_liquidity > previous_liquidity
    )
    no_new_shares = (
        "shares_outstanding" in current_financials
        and "shares_outstanding" in previous_financials
        and previous_shares > 0
        and current_shares <= previous_shares
    )
    improving_margin = (
        "gross_margin" in previous_financials and current_margin > previous_margin
    )
    improving_turnover = (
        "revenue" in previous_financials
        and "assets_total" in previous_financials
        and previous_assets > 0
        and current_turnover > previous_turnover
    )

    signal_map = {
        "positive_roa": current_roa > 0,
        "positive_cfo": current_cfo > 0,
        "improving_roa": improving_roa,
        "cfo_exceeds_roa": current_cfo_ratio > current_roa,
        "lower_leverage": lower_leverage,
        "higher_liquidity": higher_liquidity,
        "no_new_shares": no_new_shares,
        "improving_margin": improving_margin,
        "improving_turnover": improving_turnover,
    }

    f_score = sum(int(flag) for flag in signal_map.values())

    return {
        "f_score": f_score,
        **signal_map,
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
    if goodwill.is_nan() or equity <= 0:
        ratio = 0.0
    else:
        ratio = float(goodwill / equity)

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
    from datetime import datetime, timezone
    from uuid import uuid4

    red_flags = []

    # Calculate M-Score indices from real financial data
    source_name = current_report.get("report_source", "unknown")
    mscore_indices = calculate_mscore_indices(
        current_report, previous_report or {}, source_name=source_name
    )

    # Add non-calculable index warnings to red_flags
    red_flags.extend(mscore_indices["red_flags"])

    # Inject calculated indices into a copy of current_report for calculate_beneish_m_score
    enriched_current = {
        **current_report,
        "days_sales_receivables_index": mscore_indices["dsri"],
        "gross_margin_index": mscore_indices["gmi"],
        "asset_quality_index": mscore_indices["aqi"],
        "sales_growth_index": mscore_indices["sgi"],
        "depreciation_index": mscore_indices["depi"],
        "sga_expense_index": mscore_indices["sgai"],
        "leverage_index": mscore_indices["lvgi"],
        "total_accruals_to_assets": mscore_indices["tata"],
    }

    # Calculate Beneish M-Score using the real indices
    m_score_result = calculate_beneish_m_score(enriched_current, previous_report or {})
    m_score = m_score_result["m_score"]

    # Check M-Score threshold
    if m_score >= -1.78:
        red_flags.append("Beneish M-Score indicates earnings manipulation risk")

    # Calculate Piotroski F-Score
    f_score_result = calculate_piotroski_f_score(current_report, previous_report or {})
    f_score = f_score_result["f_score"]
    if f_score <= 2:
        red_flags.append(
            "Piotroski F-Score is very low, fundamentals may be deteriorating"
        )

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
    profit_cash_divergence = False
    profit_growth = 0.0
    ocf_growth = 0.0
    if previous_report:
        divergence_result = detect_profit_cash_divergence(
            Decimal(str(current_report.get("net_income", 0))),
            Decimal(str(previous_report.get("net_income", 0))),
            Decimal(str(current_report.get("operating_cash_flow", 0))),
            Decimal(str(previous_report.get("operating_cash_flow", 0))),
        )
        profit_cash_divergence = bool(divergence_result["divergence"])
        profit_growth = float(divergence_result["profit_growth"])
        ocf_growth = float(divergence_result["ocf_growth"])
        if profit_cash_divergence:
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
        audit_trail=mscore_indices["audit_trail"],
    )
    fscore_data = FScoreData(
        positive_roa=f_score_result["positive_roa"],
        positive_cfo=f_score_result["positive_cfo"],
        improving_roa=f_score_result["improving_roa"],
        cfo_exceeds_roa=f_score_result["cfo_exceeds_roa"],
        lower_leverage=f_score_result["lower_leverage"],
        higher_liquidity=f_score_result["higher_liquidity"],
        no_new_shares=f_score_result["no_new_shares"],
        improving_margin=f_score_result["improving_margin"],
        improving_turnover=f_score_result["improving_turnover"],
    )

    return RiskScore(
        score_id=uuid4(),
        ticker=current_report["ticker"],
        report_id=current_report.get("report_id", uuid4()),
        risk_level=risk_level,
        calculated_at=datetime.now(timezone.utc),
        m_score=m_score,
        mscore_data=mscore_data,
        f_score=f_score,
        fscore_data=fscore_data,
        存贷双高=存贷双高_result["存贷双高"],
        cash_amount=存贷双高_result["cash_amount"],
        debt_amount=存贷双高_result["debt_amount"],
        cash_growth_rate=存贷双高_result["cash_growth_rate"],
        debt_growth_rate=存贷双高_result["debt_growth_rate"],
        goodwill_ratio=goodwill_result["ratio"],
        goodwill_excessive=goodwill_result["excessive"],
        profit_cash_divergence=profit_cash_divergence,
        profit_growth=profit_growth,
        ocf_growth=ocf_growth,
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
