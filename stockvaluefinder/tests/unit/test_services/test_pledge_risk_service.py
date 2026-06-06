"""Tests for pledge risk calculation service.

Covers RISK-01, RISK-02, RISK-03, RISK-07, RISK-08, RISK-09.
"""

from datetime import date

import pytest

from stockvaluefinder.models.enums import DataFreshness, RiskLevel
from stockvaluefinder.models.equity_pledge import (
    CloseoutRisk,
    CompanyPledgeRisk,
    EquityPledgeDataQuality,
    HolderPledgeRisk,
    PledgeRiskGrade,
    PledgeRiskResult,
    RiskLevelBreakdown,
)


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
