"""Pledge risk calculation service - pure functions for equity pledge risk grading.

Implements RISK-01 through RISK-09 threshold-based risk grading for
company pledge ratio, controlling shareholder pledge ratio, and closeout
safety margin. All functions are synchronous with no I/O.

Follows the same pattern as risk_service.py: module-level pure functions
with a thin PledgeRiskAnalyzer class wrapper.
"""

from datetime import date

from stockvaluefinder.models.enums import DataFreshness, RiskLevel
from stockvaluefinder.models.equity_pledge import (
    CloseoutRisk,
    CompanyPledgeRisk,
    EquityPledgeDataQuality,
    EquityPledgeDetail,
    EquityPledgeSnapshot,
    HolderPledgeRisk,
    PledgeRiskResult,
    RiskLevelBreakdown,
)

# Risk level ordering for merge comparisons
_RISK_ORDER: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


# ---------------------------------------------------------------------------
# RISK-01: Company overall pledge risk grading
# ---------------------------------------------------------------------------


def determine_company_pledge_risk(
    company_pledge_ratio: float | None,
) -> tuple[RiskLevel, list[str]]:
    """Grade company overall pledge ratio into risk level.

    Thresholds from PRD section 9.1 (percentages):
        < 10%  -> LOW
        10-20% -> LOW  + note
        20-30% -> MEDIUM
        > 30%  -> HIGH

    Args:
        company_pledge_ratio: Company pledge ratio as percentage (0-100).
            None means data unavailable.

    Returns:
        Tuple of (RiskLevel, list of note strings for borderline ranges).
    """
    if company_pledge_ratio is None:
        return RiskLevel.LOW, ["质押比例数据不可得"]

    notes: list[str] = []

    if company_pledge_ratio < 10:
        level = RiskLevel.LOW
    elif company_pledge_ratio < 20:
        level = RiskLevel.LOW
        notes.append(f"公司质押比例{company_pledge_ratio:.1f}%处于10%-20%关注区间")
    elif company_pledge_ratio <= 30:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.HIGH

    return level, notes


# ---------------------------------------------------------------------------
# RISK-02: Controlling shareholder pledge risk grading
# ---------------------------------------------------------------------------


def determine_holder_pledge_risk(
    pledged_to_holding_ratio: float | None,
) -> tuple[RiskLevel, list[str]]:
    """Grade controlling shareholder pledge ratio into risk level.

    Thresholds from PRD section 9.2 (percentages):
        < 30%  -> LOW
        30-50% -> LOW  + note
        50-80% -> MEDIUM
        > 80%  -> HIGH

    Args:
        pledged_to_holding_ratio: Holder's pledged-to-holding ratio as
            percentage (0-100). None means data unavailable.

    Returns:
        Tuple of (RiskLevel, list of note strings for borderline ranges).
    """
    if pledged_to_holding_ratio is None:
        return RiskLevel.LOW, ["控股股东质押比例数据不可得"]

    notes: list[str] = []

    if pledged_to_holding_ratio < 30:
        level = RiskLevel.LOW
    elif pledged_to_holding_ratio < 50:
        level = RiskLevel.LOW
        notes.append(
            f"控股股东质押比例{pledged_to_holding_ratio:.1f}%处于30%-50%关注区间"
        )
    elif pledged_to_holding_ratio <= 80:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.HIGH

    return level, notes


# ---------------------------------------------------------------------------
# RISK-03: Closeout safety margin calculation and grading
# ---------------------------------------------------------------------------


def calculate_closeout_safety_margin(
    latest_price: float | None,
    estimated_closeout_price: float | None,
) -> float | None:
    """Calculate closeout safety margin as percentage above closeout price.

    Formula (tech design section 9.3):
        margin = (latest_price - estimated_closeout_price)
                 / estimated_closeout_price * 100

    Args:
        latest_price: Latest stock price. None means unavailable.
        estimated_closeout_price: Estimated forced-sell price. None means
            unavailable.

    Returns:
        Safety margin as percentage, or None if inputs are invalid.
    """
    if latest_price is None or estimated_closeout_price is None:
        return None
    if estimated_closeout_price <= 0:
        return None
    return (latest_price - estimated_closeout_price) / estimated_closeout_price * 100


def determine_closeout_risk(
    safety_margin: float | None,
) -> tuple[RiskLevel, list[str]]:
    """Grade closeout safety margin into risk level.

    Thresholds from PRD section 9.3 (percentages):
        > 50%  -> LOW
        30-50% -> LOW  + note
        20-30% -> MEDIUM
        < 20%  -> HIGH

    Args:
        safety_margin: Safety margin as percentage. None means data
            unavailable.

    Returns:
        Tuple of (RiskLevel, list of note strings).
    """
    if safety_margin is None:
        return RiskLevel.LOW, ["平仓线安全距离数据不可得"]

    if safety_margin > 50:
        return RiskLevel.LOW, []
    elif safety_margin >= 30:
        return RiskLevel.LOW, [f"平仓线安全距离{safety_margin:.1f}%处于30%-50%关注区间"]
    elif safety_margin >= 20:
        return RiskLevel.MEDIUM, []
    else:
        return RiskLevel.HIGH, []


# ---------------------------------------------------------------------------
# RISK-07: Data freshness classification
# ---------------------------------------------------------------------------


def determine_data_freshness(
    latest_date: date | None,
    reference_date: date | None = None,
) -> DataFreshness:
    """Classify data freshness based on calendar days since snapshot date.

    Per PRD section 11.3:
        CURRENT: within 10 calendar days (inclusive)
        STALE: older than 10 calendar days
        UNAVAILABLE: no data (latest_date is None)

    Args:
        latest_date: Trade date of the pledge data snapshot.
        reference_date: Date to compare against (defaults to date.today()).

    Returns:
        DataFreshness enum value.
    """
    if latest_date is None:
        return DataFreshness.UNAVAILABLE

    ref = reference_date or date.today()
    days_diff = (ref - latest_date).days
    if days_diff <= 10:
        return DataFreshness.CURRENT
    return DataFreshness.STALE


# ---------------------------------------------------------------------------
# RISK-08: Controlling shareholder identification
# ---------------------------------------------------------------------------


def find_controlling_holder(
    details: list[EquityPledgeDetail],
) -> EquityPledgeDetail | None:
    """Identify controlling shareholder: highest pledged_to_holding_ratio.

    Iterates over shareholder pledge details to find the one with the
    highest pledged_to_holding_ratio. This approximates "controlling
    shareholder" by pledge pressure rather than ownership stake.

    Per D-06: ties broken by first-in-list order.
    Per D-07: empty details returns None (zero-pledge stocks).

    Args:
        details: List of shareholder pledge detail records.

    Returns:
        The detail with highest pledged_to_holding_ratio, or None.
    """
    if not details:
        return None

    best: EquityPledgeDetail | None = None
    best_ratio = -1.0
    for detail in details:
        ratio = detail.pledged_to_holding_ratio
        if ratio is not None and ratio > best_ratio:
            best_ratio = ratio
            best = detail
    return best


# ---------------------------------------------------------------------------
# RISK-09: HK ticker detection
# ---------------------------------------------------------------------------


def is_hk_ticker(ticker: str) -> bool:
    """Check if ticker is a Hong Kong stock code.

    HK tickers end with '.HK' suffix. Per RISK-09, HK stocks do not
    have reliable free pledge data sources and should return
    supported=false.

    Args:
        ticker: Stock code string (e.g., '600519.SH', '00700.HK').

    Returns:
        True if the ticker is a Hong Kong stock.
    """
    return ticker.endswith(".HK")


# ---------------------------------------------------------------------------
# RISK-04: Combination upgrade rules (5 rules, all always evaluated)
# ---------------------------------------------------------------------------


def check_high_pledge_with_price_drop(
    company_pledge_ratio: float | None,
    one_year_price_change: float | None,
) -> tuple[bool, str | None]:
    """Check: company_pledge > 30% AND 1yr drop > 30%.

    Per PRD section 9.4 rule 1. Both conditions must be met.
    Returns (False, None) when inputs are insufficient.

    Args:
        company_pledge_ratio: Company pledge ratio as percentage.
        one_year_price_change: One-year price change as percentage
            (negative for drops).

    Returns:
        Tuple of (triggered, red_flag_or_none).
    """
    if company_pledge_ratio is None or one_year_price_change is None:
        return False, None
    if company_pledge_ratio > 30 and one_year_price_change < -30:
        return True, (
            f"公司质押比例{company_pledge_ratio:.1f}%"
            f"超30%且近一年跌幅{one_year_price_change:.1f}%超30%"
        )
    return False, None


def check_holder_over_80(
    holder_pledge_ratio: float | None,
) -> tuple[bool, str | None]:
    """Check: holder pledge ratio > 80%.

    Per PRD section 9.4 rule 2.
    Returns (False, None) when input is None.

    Args:
        holder_pledge_ratio: Controlling shareholder pledged-to-holding ratio.

    Returns:
        Tuple of (triggered, red_flag_or_none).
    """
    if holder_pledge_ratio is None:
        return False, None
    if holder_pledge_ratio > 80:
        return True, f"控股股东质押比例{holder_pledge_ratio:.1f}%超过80%阈值"
    return False, None


def check_closeout_margin_low(
    safety_margin: float | None,
) -> tuple[bool, str | None]:
    """Check: closeout safety margin < 20%.

    Per PRD section 9.4 rule 3.
    Returns (False, None) when input is None.

    Args:
        safety_margin: Safety margin as percentage above closeout price.

    Returns:
        Tuple of (triggered, red_flag_or_none).
    """
    if safety_margin is None:
        return False, None
    if safety_margin < 20:
        return True, f"平仓线安全距离{safety_margin:.1f}%低于20%阈值"
    return False, None


def check_high_pledge_with_financial_high(
    company_pledge_ratio: float | None,
    financial_risk_level: RiskLevel,
) -> tuple[bool, str | None]:
    """Check: company_pledge > 20% AND financial risk is HIGH or CRITICAL.

    Per PRD section 9.4 rule 4. Crosses pledge-financial boundary.
    Returns (False, None) when pledge ratio is insufficient.

    Args:
        company_pledge_ratio: Company pledge ratio as percentage.
        financial_risk_level: Financial risk level from RiskAnalyzer.

    Returns:
        Tuple of (triggered, red_flag_or_none).
    """
    if company_pledge_ratio is None:
        return False, None
    if company_pledge_ratio > 20 and financial_risk_level in (
        RiskLevel.HIGH,
        RiskLevel.CRITICAL,
    ):
        return True, (
            f"公司质押比例{company_pledge_ratio:.1f}%"
            f"超20%且财务风险为{financial_risk_level.value}"
        )
    return False, None


def check_high_pledge_with_存贷双高(
    company_pledge_ratio: float | None,
    financial_red_flags: list[str],
) -> tuple[bool, str | None]:
    """Check: company_pledge > 20% AND 存贷双高 in financial red flags.

    Per PRD section 9.4 rule 5 and pitfall 3 in RESEARCH.md.
    Matches by substring "存贷双高" in any financial red flag string.
    Returns (False, None) when pledge ratio is insufficient or no match.

    Args:
        company_pledge_ratio: Company pledge ratio as percentage.
        financial_red_flags: Financial red flags from RiskAnalyzer.

    Returns:
        Tuple of (triggered, red_flag_or_none).
    """
    if company_pledge_ratio is None:
        return False, None
    has_存贷双高 = any("存贷双高" in flag for flag in financial_red_flags)
    if company_pledge_ratio > 20 and has_存贷双高:
        return True, f"公司质押比例{company_pledge_ratio:.1f}%超20%且存在存贷双高"
    return False, None


# ---------------------------------------------------------------------------
# RISK-05: Risk level merge (pledge can only upgrade, never downgrade)
# ---------------------------------------------------------------------------


def merge_risk_levels(
    financial_risk_level: RiskLevel,
    pledge_risk_level: RiskLevel | None,
) -> tuple[RiskLevel, RiskLevelBreakdown]:
    """Merge financial and pledge risk levels.

    Per tech design section 9.5:
        - pledge_risk_level=None: return financial level unchanged.
        - Otherwise take max by _RISK_ORDER.
        - pledge can only upgrade, never downgrade financial risk.

    Args:
        financial_risk_level: Financial risk level from RiskAnalyzer.
        pledge_risk_level: Pledge risk level from grading + upgrades,
            or None when pledge data is unavailable.

    Returns:
        Tuple of (final_risk_level, RiskLevelBreakdown with details).
    """
    if pledge_risk_level is None:
        return financial_risk_level, RiskLevelBreakdown(
            financial_risk_level=financial_risk_level,
            pledge_risk_level=None,
            final_risk_level=financial_risk_level,
            merge_reason=None,
        )

    final = max(
        financial_risk_level,
        pledge_risk_level,
        key=lambda r: _RISK_ORDER[r],
    )
    reason: str | None = None
    if _RISK_ORDER[pledge_risk_level] > _RISK_ORDER[financial_risk_level]:
        reason = (
            f"质押风险{pledge_risk_level.value}"
            f"升级了财务风险{financial_risk_level.value}"
        )

    return final, RiskLevelBreakdown(
        financial_risk_level=financial_risk_level,
        pledge_risk_level=pledge_risk_level,
        final_risk_level=final,
        merge_reason=reason,
    )


# ---------------------------------------------------------------------------
# PledgeRiskAnalyzer: thin class wrapper following RiskAnalyzer pattern
# ---------------------------------------------------------------------------


class PledgeRiskAnalyzer:
    """Service class for pledge risk analysis (orchestrates pure functions).

    Stateless class following the RiskAnalyzer pattern from risk_service.py.
    The analyze() method receives already-fetched data and performs all
    grading computations synchronously with no I/O.

    Implements full pipeline: grading + combination upgrades + merge.
    """

    def __init__(self) -> None:
        """Initialize PledgeRiskAnalyzer (stateless)."""
        pass

    def analyze(
        self,
        ticker: str,
        snapshot: EquityPledgeSnapshot | None,
        details: list[EquityPledgeDetail],
        financial_risk_level: RiskLevel,
        financial_red_flags: list[str] | None = None,
    ) -> PledgeRiskResult:
        """Perform pledge risk analysis for a single stock.

        Orchestrates all grading functions, combination upgrade rules,
        and risk merge to produce a complete PledgeRiskResult.

        Pipeline order:
        1. HK check -> unsupported result
        2. Data availability -> UNAVAILABLE result
        3. Grade company risk (RISK-01)
        4. Find controlling holder (RISK-08)
        5. Grade holder risk (RISK-02)
        6. Calculate closeout margin and risk (RISK-03)
        7. Evaluate all 5 combination upgrade rules (RISK-04, D-05)
        8. Determine pledge risk level (max of dimensions + upgrades)
        9. Merge with financial risk (RISK-05)
        10. Collect red flags (RISK-06)

        Args:
            ticker: Stock code (e.g., '600519.SH').
            snapshot: Company pledge snapshot from Phase 29, or None.
            details: Shareholder pledge details from Phase 29.
            financial_risk_level: Financial risk level from RiskAnalyzer.
            financial_red_flags: Financial red flags for combination rules.

        Returns:
            PledgeRiskResult with all three dimension grades and breakdown.
        """
        flags = financial_red_flags or []

        # RISK-09: HK tickers return unsupported result
        if is_hk_ticker(ticker):
            return PledgeRiskResult(
                supported=False,
                data_quality=EquityPledgeDataQuality(
                    freshness=DataFreshness.UNAVAILABLE,
                    warnings=["港股不支持质押数据"],
                ),
                risk_level_breakdown=RiskLevelBreakdown(
                    financial_risk_level=financial_risk_level,
                    pledge_risk_level=None,
                    final_risk_level=financial_risk_level,
                    merge_reason=None,
                ),
            )

        # Compute data freshness from snapshot
        freshness = determine_data_freshness(snapshot.latest_date if snapshot else None)

        # Build data quality from snapshot or defaults
        data_quality = EquityPledgeDataQuality(
            source=snapshot.data_quality.source if snapshot else None,
            latest_date=snapshot.latest_date if snapshot else None,
            freshness=freshness,
            warnings=snapshot.data_quality.warnings if snapshot else [],
        )

        # RISK-01: Grade company pledge risk
        company_ratio = snapshot.company_pledge_ratio if snapshot else None
        company_level, company_notes = determine_company_pledge_risk(company_ratio)
        company_risk = CompanyPledgeRisk(
            risk_level=company_level,
            company_pledge_ratio=company_ratio,
            notes=company_notes,
        )

        # RISK-08: Identify controlling holder
        controlling = find_controlling_holder(details)

        # RISK-02: Grade holder pledge risk
        if controlling is not None:
            holder_ratio = controlling.pledged_to_holding_ratio
            holder_name = controlling.holder_name
            holder_level, holder_notes = determine_holder_pledge_risk(holder_ratio)
            holder_risk = HolderPledgeRisk(
                risk_level=holder_level,
                pledged_to_holding_ratio=holder_ratio,
                holder_name=holder_name,
                controlling_holder=True,
                notes=holder_notes,
            )
        else:
            # D-07: zero-pledge or no details -> LOW with no holder
            holder_risk = HolderPledgeRisk(
                risk_level=RiskLevel.LOW,
                pledged_to_holding_ratio=None,
                holder_name=None,
                controlling_holder=False,
            )

        # RISK-03: Calculate closeout safety margin from controlling holder
        if controlling is not None:
            margin = calculate_closeout_safety_margin(
                controlling.latest_price,
                controlling.estimated_closeout_price,
            )
            closeout_level, closeout_notes = determine_closeout_risk(margin)
            closeout_risk = CloseoutRisk(
                risk_level=closeout_level,
                safety_margin=margin,
                latest_price=controlling.latest_price,
                estimated_closeout_price=controlling.estimated_closeout_price,
                notes=closeout_notes,
            )
        else:
            margin = None
            closeout_risk = CloseoutRisk(
                risk_level=RiskLevel.LOW,
                safety_margin=None,
                notes=["平仓线安全距离数据不可得"],
            )

        # Collect base red flags from dimension notes
        red_flags: list[str] = list(company_risk.notes)
        red_flags.extend(holder_risk.notes)
        red_flags.extend(closeout_risk.notes)

        # RISK-04: Evaluate all 5 combination upgrade rules (no short-circuit)
        price_change = snapshot.one_year_price_change if snapshot else None
        combination_upgrades: list[str] = []

        # Rule 1: company pledge >30% + 1yr drop >30%
        r1_triggered, r1_flag = check_high_pledge_with_price_drop(
            company_ratio, price_change
        )
        if r1_triggered and r1_flag is not None:
            combination_upgrades.append(r1_flag)

        # Rule 2: holder pledge >80%
        holder_ratio_val = controlling.pledged_to_holding_ratio if controlling else None
        r2_triggered, r2_flag = check_holder_over_80(holder_ratio_val)
        if r2_triggered and r2_flag is not None:
            combination_upgrades.append(r2_flag)

        # Rule 3: closeout margin <20%
        r3_triggered, r3_flag = check_closeout_margin_low(margin)
        if r3_triggered and r3_flag is not None:
            combination_upgrades.append(r3_flag)

        # Rule 4: company pledge >20% + financial HIGH/CRITICAL
        r4_triggered, r4_flag = check_high_pledge_with_financial_high(
            company_ratio, financial_risk_level
        )
        if r4_triggered and r4_flag is not None:
            combination_upgrades.append(r4_flag)

        # Rule 5: company pledge >20% + 存贷双高
        r5_triggered, r5_flag = check_high_pledge_with_存贷双高(company_ratio, flags)
        if r5_triggered and r5_flag is not None:
            combination_upgrades.append(r5_flag)

        # Determine upgrade level from triggered rules
        # All rules target at least HIGH, so any trigger means at least HIGH
        upgrade_level = RiskLevel.HIGH if combination_upgrades else None

        # Determine overall pledge risk level (max of three dimensions + upgrade)
        # When snapshot is None (data unavailable), pledge_risk_level is None
        # to signal that pledge risk could not be assessed
        if snapshot is None:
            pledge_risk_level = None
        else:
            pledge_risk_level = max(
                company_level,
                holder_risk.risk_level,
                closeout_risk.risk_level,
                key=lambda r: _RISK_ORDER[r],
            )
            if upgrade_level is not None:
                pledge_risk_level = max(
                    pledge_risk_level,
                    upgrade_level,
                    key=lambda r: _RISK_ORDER[r],
                )

        # RISK-05: Merge financial and pledge risk levels
        _, risk_level_breakdown = merge_risk_levels(
            financial_risk_level, pledge_risk_level
        )

        # RISK-06: Collect all red flags (dimension notes + combination rules)
        red_flags.extend(combination_upgrades)

        return PledgeRiskResult(
            supported=True,
            company_risk=company_risk,
            holder_risk=holder_risk,
            closeout_risk=closeout_risk,
            combination_upgrades=combination_upgrades,
            red_flags=red_flags,
            data_quality=data_quality,
            risk_level_breakdown=risk_level_breakdown,
        )
