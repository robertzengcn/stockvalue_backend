"""Tests for pledge risk calculation service.

Covers RISK-01, RISK-02, RISK-03, RISK-07, RISK-08, RISK-09.
"""

from datetime import date, timedelta

import pytest

from stockvaluefinder.models.enums import DataFreshness, RiskLevel
from stockvaluefinder.models.equity_pledge import (
    CloseoutRisk,
    CompanyPledgeRisk,
    EquityPledgeDataQuality,
    EquityPledgeDetail,
    EquityPledgeSnapshot,
    HolderPledgeRisk,
    PledgeRiskGrade,
    PledgeRiskResult,
    RiskLevelBreakdown,
)
from stockvaluefinder.services.pledge_risk_service import (
    PledgeRiskAnalyzer,
    calculate_closeout_safety_margin,
    determine_closeout_risk,
    determine_company_pledge_risk,
    determine_data_freshness,
    determine_holder_pledge_risk,
    find_controlling_holder,
    is_hk_ticker,
)


# ---------------------------------------------------------------------------
# Task 1: Model tests
# ---------------------------------------------------------------------------


class TestPledgeRiskModels:
    """Test pledge risk result model instantiation and constraints."""

    def test_pledge_risk_grade_basic(self) -> None:
        """PledgeRiskGrade instantiates with risk_level and notes."""
        grade = PledgeRiskGrade(risk_level=RiskLevel.LOW, notes=[])
        assert grade.risk_level == RiskLevel.LOW
        assert grade.notes == []

    def test_company_pledge_risk(self) -> None:
        """CompanyPledgeRisk instantiates with risk_level, ratio, and notes."""
        risk = CompanyPledgeRisk(
            risk_level=RiskLevel.HIGH,
            company_pledge_ratio=35.5,
            notes=["公司质押比例35.5%超过30%阈值"],
        )
        assert risk.risk_level == RiskLevel.HIGH
        assert risk.company_pledge_ratio == 35.5
        assert len(risk.notes) == 1

    def test_holder_pledge_risk(self) -> None:
        """HolderPledgeRisk instantiates with risk_level, ratio, holder_name, notes, controlling."""
        risk = HolderPledgeRisk(
            risk_level=RiskLevel.MEDIUM,
            pledged_to_holding_ratio=65.0,
            holder_name="张三",
            controlling_holder=True,
            notes=["控股股东质押比例65.0%处于50%-80%风险区间"],
        )
        assert risk.risk_level == RiskLevel.MEDIUM
        assert risk.pledged_to_holding_ratio == 65.0
        assert risk.holder_name == "张三"
        assert risk.controlling_holder is True
        assert len(risk.notes) == 1

    def test_closeout_risk(self) -> None:
        """CloseoutRisk instantiates with risk_level, safety_margin, prices, notes."""
        risk = CloseoutRisk(
            risk_level=RiskLevel.LOW,
            safety_margin=60.0,
            latest_price=16.0,
            estimated_closeout_price=10.0,
            notes=[],
        )
        assert risk.risk_level == RiskLevel.LOW
        assert risk.safety_margin == 60.0
        assert risk.latest_price == 16.0
        assert risk.estimated_closeout_price == 10.0

    def test_closeout_risk_with_none_margin(self) -> None:
        """CloseoutRisk accepts None safety_margin for data-unavailable cases."""
        risk = CloseoutRisk(
            risk_level=RiskLevel.LOW,
            safety_margin=None,
            latest_price=None,
            estimated_closeout_price=None,
            notes=["平仓线安全距离数据不可得"],
        )
        assert risk.safety_margin is None
        assert risk.latest_price is None

    def test_risk_level_breakdown(self) -> None:
        """RiskLevelBreakdown instantiates with financial, pledge, final levels, and merge_reason."""
        breakdown = RiskLevelBreakdown(
            financial_risk_level=RiskLevel.MEDIUM,
            pledge_risk_level=RiskLevel.HIGH,
            final_risk_level=RiskLevel.HIGH,
            merge_reason="质押风险HIGH升级了财务风险MEDIUM",
        )
        assert breakdown.financial_risk_level == RiskLevel.MEDIUM
        assert breakdown.pledge_risk_level == RiskLevel.HIGH
        assert breakdown.final_risk_level == RiskLevel.HIGH
        assert breakdown.merge_reason is not None
        assert "升级" in breakdown.merge_reason

    def test_risk_level_breakdown_no_upgrade(self) -> None:
        """RiskLevelBreakdown with no merge has None reason."""
        breakdown = RiskLevelBreakdown(
            financial_risk_level=RiskLevel.HIGH,
            pledge_risk_level=RiskLevel.LOW,
            final_risk_level=RiskLevel.HIGH,
            merge_reason=None,
        )
        assert breakdown.merge_reason is None

    def test_pledge_risk_result_supported(self) -> None:
        """PledgeRiskResult instantiates with all fields, supported=True."""
        quality = EquityPledgeDataQuality(
            source="akshare",
            latest_date=date(2026, 6, 5),
            freshness=DataFreshness.CURRENT,
        )
        company_risk = CompanyPledgeRisk(
            risk_level=RiskLevel.LOW,
            company_pledge_ratio=5.0,
        )
        holder_risk = HolderPledgeRisk(
            risk_level=RiskLevel.LOW,
            pledged_to_holding_ratio=20.0,
            holder_name=None,
            controlling_holder=False,
        )
        closeout_risk = CloseoutRisk(
            risk_level=RiskLevel.LOW,
            safety_margin=None,
        )
        breakdown = RiskLevelBreakdown(
            financial_risk_level=RiskLevel.LOW,
            pledge_risk_level=RiskLevel.LOW,
            final_risk_level=RiskLevel.LOW,
        )
        result = PledgeRiskResult(
            supported=True,
            company_risk=company_risk,
            holder_risk=holder_risk,
            closeout_risk=closeout_risk,
            red_flags=[],
            data_quality=quality,
            risk_level_breakdown=breakdown,
        )
        assert result.supported is True
        assert result.company_risk is not None
        assert result.holder_risk is not None
        assert result.closeout_risk is not None
        assert result.red_flags == []
        assert result.data_quality.freshness == DataFreshness.CURRENT

    def test_pledge_risk_result_frozen(self) -> None:
        """PledgeRiskResult is frozen=True and rejects mutation."""
        quality = EquityPledgeDataQuality(freshness=DataFreshness.CURRENT)
        breakdown = RiskLevelBreakdown(
            financial_risk_level=RiskLevel.LOW,
            pledge_risk_level=RiskLevel.LOW,
            final_risk_level=RiskLevel.LOW,
        )
        result = PledgeRiskResult(
            supported=True,
            data_quality=quality,
            risk_level_breakdown=breakdown,
        )
        with pytest.raises(Exception):
            result.supported = False  # type: ignore[misc]

    def test_pledge_risk_result_unsupported_has_warning(self) -> None:
        """PledgeRiskResult with supported=False has warning in data_quality."""
        quality = EquityPledgeDataQuality(
            freshness=DataFreshness.UNAVAILABLE,
            warnings=["港股不支持质押数据"],
        )
        breakdown = RiskLevelBreakdown(
            financial_risk_level=RiskLevel.LOW,
            pledge_risk_level=None,
            final_risk_level=RiskLevel.LOW,
        )
        result = PledgeRiskResult(
            supported=False,
            data_quality=quality,
            risk_level_breakdown=breakdown,
        )
        assert result.supported is False
        assert "港股不支持质押数据" in result.data_quality.warnings
        assert result.company_risk is None
        assert result.holder_risk is None
        assert result.closeout_risk is None


# ---------------------------------------------------------------------------
# Task 2: Pure grading function tests
# ---------------------------------------------------------------------------


class TestCompanyPledgeRisk:
    """RISK-01: Company pledge ratio risk grading thresholds."""

    @pytest.mark.parametrize(
        ("ratio", "expected_level", "should_have_note"),
        [
            (None, RiskLevel.LOW, True),  # data unavailable
            (5.0, RiskLevel.LOW, False),  # <10%
            (15.0, RiskLevel.LOW, True),  # 10-20% with note
            (25.0, RiskLevel.MEDIUM, False),  # 20-30%
            (35.0, RiskLevel.HIGH, False),  # >30%
            (10.0, RiskLevel.LOW, True),  # exact boundary 10%
            (20.0, RiskLevel.MEDIUM, False),  # exact boundary 20%
            (30.0, RiskLevel.MEDIUM, False),  # exact boundary 30%
            (9.9, RiskLevel.LOW, False),  # just under 10%
            (20.1, RiskLevel.MEDIUM, False),  # just over 20%
            (30.1, RiskLevel.HIGH, False),  # just over 30%
            (0.0, RiskLevel.LOW, False),  # zero pledge
        ],
    )
    def test_company_pledge_risk_grading(
        self,
        ratio: float | None,
        expected_level: RiskLevel,
        should_have_note: bool,
    ) -> None:
        """Grade company pledge ratio at threshold boundaries."""
        level, notes = determine_company_pledge_risk(ratio)
        assert level == expected_level
        if should_have_note:
            assert len(notes) > 0
        else:
            assert len(notes) == 0

    def test_none_returns_unavailable_note(self) -> None:
        """None ratio returns LOW with data-unavailable note."""
        level, notes = determine_company_pledge_risk(None)
        assert level == RiskLevel.LOW
        assert any("不可得" in n for n in notes)

    def test_10_20_range_note_content(self) -> None:
        """10-20% range note mentions the range."""
        _, notes = determine_company_pledge_risk(15.0)
        assert len(notes) == 1
        assert "10%-20%" in notes[0] or "10%" in notes[0]


class TestHolderPledgeRisk:
    """RISK-02: Controlling shareholder pledge ratio risk grading thresholds."""

    @pytest.mark.parametrize(
        ("ratio", "expected_level", "should_have_note"),
        [
            (None, RiskLevel.LOW, True),  # data unavailable
            (20.0, RiskLevel.LOW, False),  # <30%
            (40.0, RiskLevel.LOW, True),  # 30-50% with note
            (65.0, RiskLevel.MEDIUM, False),  # 50-80%
            (85.0, RiskLevel.HIGH, False),  # >80%
            (30.0, RiskLevel.LOW, True),  # exact boundary 30%
            (50.0, RiskLevel.MEDIUM, False),  # exact boundary 50%
            (80.0, RiskLevel.MEDIUM, False),  # exact boundary 80%
            (29.9, RiskLevel.LOW, False),  # just under 30%
            (50.1, RiskLevel.MEDIUM, False),  # just over 50%
            (80.1, RiskLevel.HIGH, False),  # just over 80%
        ],
    )
    def test_holder_pledge_risk_grading(
        self,
        ratio: float | None,
        expected_level: RiskLevel,
        should_have_note: bool,
    ) -> None:
        """Grade holder pledge ratio at threshold boundaries."""
        level, notes = determine_holder_pledge_risk(ratio)
        assert level == expected_level
        if should_have_note:
            assert len(notes) > 0
        else:
            assert len(notes) == 0

    def test_none_returns_unavailable_note(self) -> None:
        """None ratio returns LOW with data-unavailable note."""
        level, notes = determine_holder_pledge_risk(None)
        assert level == RiskLevel.LOW
        assert any("不可得" in n for n in notes)

    def test_30_50_range_note_content(self) -> None:
        """30-50% range note mentions the range."""
        _, notes = determine_holder_pledge_risk(40.0)
        assert len(notes) == 1
        assert "30%-50%" in notes[0] or "30%" in notes[0]


class TestCloseoutMargin:
    """RISK-03: Closeout safety margin calculation and risk grading."""

    # --- calculate_closeout_safety_margin ---

    def test_margin_normal(self) -> None:
        """(10.0, 8.0) -> 25.0."""
        assert calculate_closeout_safety_margin(10.0, 8.0) == 25.0

    def test_margin_none_latest_price(self) -> None:
        """None latest_price returns None."""
        assert calculate_closeout_safety_margin(None, 8.0) is None

    def test_margin_none_closeout_price(self) -> None:
        """None estimated_closeout_price returns None."""
        assert calculate_closeout_safety_margin(10.0, None) is None

    def test_margin_zero_closeout_price(self) -> None:
        """Zero closeout_price returns None (division guard)."""
        assert calculate_closeout_safety_margin(10.0, 0.0) is None

    def test_margin_both_none(self) -> None:
        """Both None returns None."""
        assert calculate_closeout_safety_margin(None, None) is None

    def test_margin_negative_result(self) -> None:
        """Price below closeout price yields negative margin."""
        result = calculate_closeout_safety_margin(8.0, 10.0)
        assert result is not None
        assert result < 0

    # --- determine_closeout_risk ---

    @pytest.mark.parametrize(
        ("margin", "expected_level", "should_have_note"),
        [
            (60.0, RiskLevel.LOW, False),  # >50%
            (40.0, RiskLevel.LOW, True),  # 30-50% with note
            (25.0, RiskLevel.MEDIUM, False),  # 20-30%
            (15.0, RiskLevel.HIGH, False),  # <20%
            (None, RiskLevel.LOW, True),  # data unavailable
            (50.0, RiskLevel.LOW, True),  # exact boundary 50%
            (30.0, RiskLevel.LOW, True),  # exact boundary 30%
            (20.0, RiskLevel.MEDIUM, False),  # exact boundary 20%
            (50.1, RiskLevel.LOW, False),  # just over 50%
            (19.9, RiskLevel.HIGH, False),  # just under 20%
        ],
    )
    def test_closeout_risk_grading(
        self,
        margin: float | None,
        expected_level: RiskLevel,
        should_have_note: bool,
    ) -> None:
        """Grade closeout margin at threshold boundaries."""
        level, notes = determine_closeout_risk(margin)
        assert level == expected_level
        if should_have_note:
            assert len(notes) > 0
        else:
            assert len(notes) == 0

    def test_none_margin_returns_unavailable_note(self) -> None:
        """None margin returns LOW with data-unavailable note."""
        level, notes = determine_closeout_risk(None)
        assert level == RiskLevel.LOW
        assert any("不可得" in n for n in notes)


class TestDataFreshness:
    """RISK-07: Data freshness classification based on calendar days."""

    def test_none_date_returns_unavailable(self) -> None:
        """None latest_date returns UNAVAILABLE."""
        assert determine_data_freshness(None) == DataFreshness.UNAVAILABLE

    def test_today_returns_current(self) -> None:
        """Today's date returns CURRENT."""
        today = date(2026, 6, 6)
        assert (
            determine_data_freshness(today, reference_date=today)
            == DataFreshness.CURRENT
        )

    def test_5_days_ago_returns_current(self) -> None:
        """5 days ago returns CURRENT."""
        ref = date(2026, 6, 6)
        latest = ref - timedelta(days=5)
        assert (
            determine_data_freshness(latest, reference_date=ref)
            == DataFreshness.CURRENT
        )

    def test_10_days_ago_returns_current(self) -> None:
        """Exactly 10 days ago returns CURRENT (boundary)."""
        ref = date(2026, 6, 6)
        latest = ref - timedelta(days=10)
        assert (
            determine_data_freshness(latest, reference_date=ref)
            == DataFreshness.CURRENT
        )

    def test_11_days_ago_returns_stale(self) -> None:
        """11 days ago returns STALE."""
        ref = date(2026, 6, 6)
        latest = ref - timedelta(days=11)
        assert (
            determine_data_freshness(latest, reference_date=ref) == DataFreshness.STALE
        )

    def test_future_date_returns_current(self) -> None:
        """Future date returns CURRENT (negative diff)."""
        ref = date(2026, 6, 6)
        future = ref + timedelta(days=1)
        assert (
            determine_data_freshness(future, reference_date=ref)
            == DataFreshness.CURRENT
        )

    def test_no_reference_defaults_to_today(self) -> None:
        """When no reference_date is given, uses today's date."""
        today = date.today()
        # 5 days ago should be CURRENT regardless
        latest = today - timedelta(days=5)
        assert determine_data_freshness(latest) == DataFreshness.CURRENT


class TestFindControllingHolder:
    """RISK-08: Identify controlling shareholder by highest pledged_to_holding_ratio."""

    def _make_detail(
        self,
        holder_name: str,
        ratio: float | None,
    ) -> EquityPledgeDetail:
        return EquityPledgeDetail(
            ticker="600519.SH",
            holder_name=holder_name,
            pledged_to_holding_ratio=ratio,
            source="akshare",
        )

    def test_empty_list_returns_none(self) -> None:
        """Empty list returns None (D-07 zero-pledge)."""
        assert find_controlling_holder([]) is None

    def test_single_detail_returns_that(self) -> None:
        """Single detail with ratio returns that detail."""
        detail = self._make_detail("张三", 50.0)
        result = find_controlling_holder([detail])
        assert result is not None
        assert result.holder_name == "张三"
        assert result.pledged_to_holding_ratio == 50.0

    def test_multiple_returns_highest_ratio(self) -> None:
        """Multiple details returns the one with highest ratio."""
        d1 = self._make_detail("张三", 30.0)
        d2 = self._make_detail("李四", 80.0)
        d3 = self._make_detail("王五", 50.0)
        result = find_controlling_holder([d1, d2, d3])
        assert result is not None
        assert result.holder_name == "李四"

    def test_tie_returns_first_in_list(self) -> None:
        """Tie in ratio returns first in list order (D-06)."""
        d1 = self._make_detail("张三", 80.0)
        d2 = self._make_detail("李四", 80.0)
        result = find_controlling_holder([d1, d2])
        assert result is not None
        assert result.holder_name == "张三"

    def test_all_none_ratios_returns_none(self) -> None:
        """All details with None ratios returns None."""
        d1 = self._make_detail("张三", None)
        d2 = self._make_detail("李四", None)
        result = find_controlling_holder([d1, d2])
        assert result is None

    def test_mixed_none_and_values(self) -> None:
        """Details with mixed None and values picks highest non-None."""
        d1 = self._make_detail("张三", None)
        d2 = self._make_detail("李四", 60.0)
        d3 = self._make_detail("王五", None)
        result = find_controlling_holder([d1, d2, d3])
        assert result is not None
        assert result.holder_name == "李四"


class TestHKTicker:
    """RISK-09: HK ticker detection."""

    @pytest.mark.parametrize(
        ("ticker", "expected"),
        [
            ("00700.HK", True),
            ("600519.SH", False),
            ("000002.SZ", False),
            ("123456.HK", True),
            ("600519.SS", False),
        ],
    )
    def test_is_hk_ticker(self, ticker: str, expected: bool) -> None:
        """Detect HK tickers by suffix."""
        assert is_hk_ticker(ticker) == expected


class TestPledgeRiskAnalyzerBasic:
    """Basic PledgeRiskAnalyzer tests for orchestration and HK handling."""

    def _make_snapshot(
        self,
        company_pledge_ratio: float | None = 5.0,
        latest_date: date | None = None,
        one_year_price_change: float | None = None,
    ) -> EquityPledgeSnapshot:
        if latest_date is None:
            latest_date = date(2026, 6, 5)
        return EquityPledgeSnapshot(
            ticker="600519.SH",
            latest_date=latest_date,
            company_pledge_ratio=company_pledge_ratio,
            one_year_price_change=one_year_price_change,
            data_quality=EquityPledgeDataQuality(
                source="akshare",
                latest_date=latest_date,
                freshness=DataFreshness.CURRENT,
            ),
        )

    def _make_detail(
        self,
        holder_name: str = "张三",
        pledged_to_holding_ratio: float | None = 20.0,
        latest_price: float | None = None,
        estimated_closeout_price: float | None = None,
    ) -> EquityPledgeDetail:
        return EquityPledgeDetail(
            ticker="600519.SH",
            holder_name=holder_name,
            pledged_to_holding_ratio=pledged_to_holding_ratio,
            latest_price=latest_price,
            estimated_closeout_price=estimated_closeout_price,
            source="akshare",
        )

    def test_analyzer_returns_result_for_a_share(self) -> None:
        """Analyzer returns PledgeRiskResult for A-share ticker."""
        analyzer = PledgeRiskAnalyzer()
        snapshot = self._make_snapshot()
        result = analyzer.analyze(
            ticker="600519.SH",
            snapshot=snapshot,
            details=[self._make_detail()],
            financial_risk_level=RiskLevel.LOW,
        )
        assert isinstance(result, PledgeRiskResult)
        assert result.supported is True
        assert result.company_risk is not None
        assert result.holder_risk is not None
        assert result.closeout_risk is not None
        assert result.risk_level_breakdown is not None

    def test_analyzer_hk_ticker_returns_unsupported(self) -> None:
        """Analyzer returns supported=False for HK ticker."""
        analyzer = PledgeRiskAnalyzer()
        result = analyzer.analyze(
            ticker="00700.HK",
            snapshot=None,
            details=[],
            financial_risk_level=RiskLevel.LOW,
        )
        assert result.supported is False
        assert result.company_risk is None
        assert result.holder_risk is None
        assert result.closeout_risk is None
        assert result.data_quality.freshness == DataFreshness.UNAVAILABLE

    def test_analyzer_none_snapshot(self) -> None:
        """Analyzer handles None snapshot gracefully."""
        analyzer = PledgeRiskAnalyzer()
        result = analyzer.analyze(
            ticker="600519.SH",
            snapshot=None,
            details=[],
            financial_risk_level=RiskLevel.LOW,
        )
        assert result.supported is True
        assert result.data_quality.freshness == DataFreshness.UNAVAILABLE
        assert result.company_risk is not None
        assert result.company_risk.risk_level == RiskLevel.LOW

    def test_analyzer_zero_pledge_details(self) -> None:
        """Analyzer handles zero-pledge (empty details) with LOW holder risk (D-07)."""
        analyzer = PledgeRiskAnalyzer()
        snapshot = self._make_snapshot(company_pledge_ratio=0.0)
        result = analyzer.analyze(
            ticker="600519.SH",
            snapshot=snapshot,
            details=[],
            financial_risk_level=RiskLevel.LOW,
        )
        assert result.holder_risk is not None
        assert result.holder_risk.risk_level == RiskLevel.LOW
        assert result.holder_risk.holder_name is None
        assert result.holder_risk.controlling_holder is False

    def test_analyzer_identifies_controlling_holder(self) -> None:
        """Analyzer identifies controlling holder from details."""
        analyzer = PledgeRiskAnalyzer()
        snapshot = self._make_snapshot()
        d1 = self._make_detail(holder_name="张三", pledged_to_holding_ratio=30.0)
        d2 = self._make_detail(holder_name="李四", pledged_to_holding_ratio=70.0)
        result = analyzer.analyze(
            ticker="600519.SH",
            snapshot=snapshot,
            details=[d1, d2],
            financial_risk_level=RiskLevel.LOW,
        )
        assert result.holder_risk is not None
        assert result.holder_risk.holder_name == "李四"
        assert result.holder_risk.controlling_holder is True

    def test_analyzer_closeout_margin_with_prices(self) -> None:
        """Analyzer calculates closeout margin when prices are available."""
        analyzer = PledgeRiskAnalyzer()
        snapshot = self._make_snapshot()
        detail = self._make_detail(
            latest_price=12.0,
            estimated_closeout_price=10.0,
        )
        result = analyzer.analyze(
            ticker="600519.SH",
            snapshot=snapshot,
            details=[detail],
            financial_risk_level=RiskLevel.LOW,
        )
        assert result.closeout_risk is not None
        assert result.closeout_risk.safety_margin == 20.0

    def test_analyzer_high_company_pledge(self) -> None:
        """Analyzer grades HIGH for company pledge ratio >30%."""
        analyzer = PledgeRiskAnalyzer()
        snapshot = self._make_snapshot(company_pledge_ratio=35.0)
        result = analyzer.analyze(
            ticker="600519.SH",
            snapshot=snapshot,
            details=[],
            financial_risk_level=RiskLevel.LOW,
        )
        assert result.company_risk is not None
        assert result.company_risk.risk_level == RiskLevel.HIGH

    def test_analyzer_data_freshness_computed(self) -> None:
        """Analyzer computes data freshness from snapshot date."""
        analyzer = PledgeRiskAnalyzer()
        ref_date = date(2026, 6, 6)
        snapshot = self._make_snapshot(latest_date=ref_date)
        result = analyzer.analyze(
            ticker="600519.SH",
            snapshot=snapshot,
            details=[],
            financial_risk_level=RiskLevel.LOW,
        )
        assert result.data_quality.freshness == DataFreshness.CURRENT
